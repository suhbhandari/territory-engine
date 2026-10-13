"""
Signal: Open job postings from the account's own careers page
Fetches the account's website, finds its careers page, detects the applicant-tracking
system (ATS) behind it, and counts open postings where the ATS publishes a readable feed.
Titles are classified into role buckets defined in the vertical's signals.yaml.

fetch(account, params) -> dict with keys:
  jobs_status, jobs_ats, jobs_source_url, jobs_total, jobs_total_all_locations,
  jobs_<bucket> for each bucket in params["role_keywords"], jobs_titles_sample

jobs_status says how far the lookup got, so "no postings" is never confused with "not checked":
  no_website                account has no website on file; nothing was fetched
  site_unreachable          website did not respond, or refused the request, while our own
                            connection was working (if it was not, the signal raises and
                            the account is retried on the next run)
  robots_disallowed         the site's robots.txt asks crawlers not to fetch it
  no_careers_page           site loaded, no careers/jobs link found
  careers_page_no_listings  careers page found, no ATS or structured listings on it
  offsite_listings          careers page points to an external job board (not followed)
  ats_unsupported           ATS identified (see jobs_ats) but it has no feed read here
  listings_found            postings seen in the pages' structured data, or an ATS feed too
                            long to read in full; jobs_total is a floor, not a count
  counted                   full ATS feed read; jobs_total is the count in the account's area

Only first-party pages and the ATS feeds they embed are read. External job boards are
never fetched. robots.txt is honoured and requests to one host are spaced out.
"""

import json
import re
import threading
import time
from collections import defaultdict
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from src.signals.online import require_online

_UA = "territory-engine/1.0 (account research; honours robots.txt)"
_HEADERS = {"User-Agent": _UA, "Accept": "text/html,application/json;q=0.9,*/*;q=0.5"}
_TIMEOUT = 12
_HOST_DELAY = 1.5
_MAX_PAGES = 6
_MAX_BYTES = 3_000_000
_FEED_PAGE_LIMIT = 60
_SAMPLE_SIZE = 5

_CAREER_WORDS = (
    "career", "job", "employment", "join our team", "join-our-team", "join us", "join-us",
    "work with us", "work-with-us", "work for us", "work-for-us", "hiring",
    "open positions", "open-positions", "openings",
)
_SKIP_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".doc", ".docx", ".zip", ".mp4")

# ATS vendors recognised by the domains their embeds and links use.
_ATS_DOMAINS = {
    "greenhouse.io": "Greenhouse",
    "lever.co": "Lever",
    "myworkdayjobs.com": "Workday",
    "icims.com": "iCIMS",
    "ultipro.com": "UKG",
    "ukg.com": "UKG",
    "workforcenow.adp.com": "ADP",
    "paycomonline.net": "Paycom",
    "paylocity.com": "Paylocity",
    "bamboohr.com": "BambooHR",
    "smartrecruiters.com": "SmartRecruiters",
    "workable.com": "Workable",
    "applytojob.com": "JazzHR",
    "apploi.com": "Apploi",
    "hireology.com": "Hireology",
    "breezy.hr": "Breezy",
    "recruitee.com": "Recruitee",
    "ashbyhq.com": "Ashby",
    "jobvite.com": "Jobvite",
    "taleo.net": "Taleo",
    "isolvedhire.com": "isolved",
    "careerplug.com": "CareerPlug",
    "paycor.com": "Paycor",
    "applicantpro.com": "ApplicantPro",
}
_JOB_BOARDS = ("indeed.com", "ziprecruiter.com", "linkedin.com/jobs", "glassdoor.com", "simplyhired.com", "monster.com")

_GREENHOUSE = re.compile(r"greenhouse\.io/(?:embed/job_board(?:/js)?\?for=|v1/boards/)?([a-z0-9_-]+)", re.I)
_GREENHOUSE_RESERVED = {"embed", "v1", "job_board", "js", "boards"}
_LEVER = re.compile(r"jobs\.lever\.co/([A-Za-z0-9_.-]+)")
_WORKDAY = re.compile(r"https?://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)")
_JSON_LD = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)

_STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

_host_locks = defaultdict(threading.Lock)
_host_last = {}
_robots = {}
_site_locks = defaultdict(threading.Lock)
_site_cache = {}


class _Unreachable(Exception):
    pass


def fetch(account: dict, params: dict) -> dict:
    role_keywords = params.get("role_keywords", {})
    result = {
        "jobs_status": "no_website",
        "jobs_ats": None,
        "jobs_source_url": None,
        "jobs_total": None,
        "jobs_total_all_locations": None,
    }
    for bucket in role_keywords:
        result[f"jobs_{bucket}"] = None
    result["jobs_titles_sample"] = None

    url = (account.get("website") or "").strip()
    if not url:
        return result
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    site = _crawl_cached(url)
    result["jobs_status"] = site["status"]
    result["jobs_ats"] = site["ats"]
    result["jobs_source_url"] = site["source_url"]

    if site["status"] not in ("counted", "listings_found"):
        return result

    postings = site["postings"]
    local = [p for p in postings if _in_area(p["location"], account)]
    titles = [p["title"] for p in local]
    result["jobs_total"] = len(local)
    result["jobs_total_all_locations"] = site["total"]
    result["jobs_titles_sample"] = "; ".join(titles[:_SAMPLE_SIZE])
    for bucket, keywords in role_keywords.items():
        result[f"jobs_{bucket}"] = sum(
            1 for t in titles if any(kw.lower() in t.lower() for kw in keywords)
        )
    return result


def _crawl_cached(url: str) -> dict:
    parsed = urlparse(url)
    key = parsed.netloc.lower().replace("www.", "") + parsed.path.rstrip("/")
    with _site_locks[key]:
        if key not in _site_cache:
            _site_cache[key] = _crawl(url)
        return _site_cache[key]


def _crawl(url: str) -> dict:
    site = {"status": "no_careers_page", "ats": None, "source_url": None, "postings": [], "total": None}

    try:
        home_url, home_html = _get_page(url)
    except PermissionError:
        site["status"] = "robots_disallowed"
        return site
    except _Unreachable:
        site["status"] = "site_unreachable"
        return site

    base = _base_domain(home_url)
    pages = [(home_url, home_html, False)]
    seen = {_norm(home_url), _norm(url)}
    queue = _career_links(home_url, home_html, base, seen)[:3]

    while queue and len(pages) < _MAX_PAGES:
        link = queue.pop(0)
        if _norm(link) in seen:
            continue
        seen.add(_norm(link))
        try:
            page_url, html = _get_page(link)
        except (PermissionError, _Unreachable):
            continue
        pages.append((page_url, html, True))
        queue.extend(l for l in _career_links(page_url, html, base, seen)[:2] if l not in queue)

    careers_pages = [p for p in pages if p[2]]
    # Careers pages first: an ATS or job-board link there outranks one in a homepage footer.
    ordered = careers_pages + [p for p in pages if not p[2]]

    for page_url, html, _ in ordered:
        feed = _read_feed(html)
        if feed:
            status = "counted" if len(feed[1]) >= feed[2] else "listings_found"
            site.update(status=status, ats=feed[0], source_url=page_url, postings=feed[1], total=feed[2])
            return site

    found = {}
    for page_url, html, _ in ordered:
        for posting in _json_ld_postings(html):
            found.setdefault((posting["title"], posting["location"]), (posting, page_url))
    if found:
        postings = [p for p, _ in found.values()]
        site.update(status="listings_found", source_url=next(iter(found.values()))[1], postings=postings, total=len(postings))
        return site

    for page_url, html, _ in ordered:
        ats = _detect_ats(html)
        if ats:
            site.update(status="ats_unsupported", ats=ats, source_url=page_url)
            return site

    for page_url, html, _ in ordered:
        if any(board in html for board in _JOB_BOARDS):
            site.update(status="offsite_listings", source_url=page_url)
            return site

    if careers_pages:
        site.update(status="careers_page_no_listings", source_url=careers_pages[0][0])
    return site


def _read_feed(html: str):
    m = _WORKDAY.search(html)
    if m:
        postings, total = _workday(*m.groups())
        return "Workday", postings, total

    m = _LEVER.search(html)
    if m:
        data = _get_json(f"https://api.lever.co/v0/postings/{m.group(1)}?mode=json")
        postings = [
            {"title": j.get("text", ""), "location": (j.get("categories") or {}).get("location", "") or ""}
            for j in data
        ]
        return "Lever", postings, len(postings)

    for token in _GREENHOUSE.findall(html):
        if token.lower() in _GREENHOUSE_RESERVED:
            continue
        data = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
        postings = [
            {"title": j.get("title", ""), "location": (j.get("location") or {}).get("name", "") or ""}
            for j in data.get("jobs", [])
        ]
        return "Greenhouse", postings, len(postings)

    return None


def _workday(tenant: str, pod: str, board: str):
    api = f"https://{tenant}.{pod}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs"
    postings, total = [], 0
    for page in range(_FEED_PAGE_LIMIT):
        data = _get_json(api, body={"appliedFacets": {}, "limit": 20, "offset": page * 20, "searchText": ""})
        batch = data.get("jobPostings", [])
        # Only the first page reports the true total; later pages return 0.
        total = total or data.get("total", 0)
        postings.extend({"title": j.get("title", ""), "location": j.get("locationsText", "") or ""} for j in batch)
        if len(batch) < 20 or len(postings) >= total:
            break
    return postings, total or len(postings)


def _json_ld_postings(html: str) -> list:
    postings = []
    for block in _JSON_LD.findall(html):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                if node.get("@type") == "JobPosting" and node.get("title"):
                    postings.append({"title": str(node["title"]), "location": _ld_location(node.get("jobLocation"))})
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
    return postings


def _ld_location(loc) -> str:
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if not isinstance(loc, dict):
        return ""
    addr = loc.get("address")
    if not isinstance(addr, dict):
        return str(addr or "")
    return ", ".join(str(addr[k]) for k in ("addressLocality", "addressRegion") if addr.get(k))


def _detect_ats(html: str):
    lowered = html.lower()
    for domain, name in _ATS_DOMAINS.items():
        if domain in lowered:
            return name
    return None


def _in_area(location: str, account: dict) -> bool:
    if not location.strip():
        return True
    state = account.get("state", "")
    city = account.get("city", "")
    if state and re.search(rf"\b{re.escape(state)}\b", location):
        return True
    if state in _STATE_NAMES and _STATE_NAMES[state].lower() in location.lower():
        return True
    return bool(city) and city.lower() in location.lower()


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self._href = attrs["href"]
            self._text = []
        elif tag in ("frame", "iframe") and attrs.get("src"):
            self.links.append((attrs["src"], attrs.get("name") or attrs.get("title") or ""))

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text)))
            self._href = None


def _career_links(page_url: str, html: str, base: str, seen: set) -> list:
    parser = _LinkParser()
    try:
        parser.feed(html)
    except Exception:
        return []

    scored = {}
    for href, text in parser.links:
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        link = urljoin(page_url, href).split("#")[0]
        parsed = urlparse(link)
        if parsed.scheme not in ("http", "https") or _base_domain(link) != base:
            continue
        if parsed.path.lower().endswith(_SKIP_EXT) or _norm(link) in seen:
            continue
        path = parsed.path.lower()
        label = " ".join(text.lower().split())
        in_path = any(w in path for w in _CAREER_WORDS) or any(w in parsed.netloc.lower() for w in ("career", "job"))
        in_label = any(w in label for w in _CAREER_WORDS)
        if not (in_path or in_label):
            continue
        score = (0 if in_path and in_label else 1, len(path))
        if link not in scored or score < scored[link]:
            scored[link] = score
    return sorted(scored, key=scored.get)


def _base_domain(url: str) -> str:
    return ".".join(urlparse(url).netloc.lower().split(":")[0].split(".")[-2:])


def _norm(url: str) -> str:
    p = urlparse(url)
    return p.netloc.lower().replace("www.", "") + p.path.rstrip("/") + ("?" + p.query if p.query else "")


def _allowed(url: str) -> bool:
    parsed = urlparse(url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    if root not in _robots:
        rp = RobotFileParser()
        try:
            resp = requests.get(root + "/robots.txt", headers=_HEADERS, timeout=_TIMEOUT)
            rp.parse(resp.text.splitlines() if resp.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])
        _robots[root] = rp
    return _robots[root].can_fetch(_UA, url)


def _request(method: str, url: str, **kwargs):
    host = urlparse(url).netloc
    with _host_locks[host]:
        if not _allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        wait = _host_last.get(host, 0) + _HOST_DELAY - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            return requests.request(method, url, headers=_HEADERS, timeout=_TIMEOUT, **kwargs)
        finally:
            _host_last[host] = time.monotonic()


def _get_page(url: str):
    try:
        resp = _request("GET", url, allow_redirects=True, stream=True)
        if resp.status_code >= 400:
            raise _Unreachable(f"{resp.status_code} for {url}")
        if "html" not in resp.headers.get("Content-Type", "html"):
            raise _Unreachable(f"not html: {url}")
        body = resp.raw.read(_MAX_BYTES, decode_content=True)
        return resp.url, body.decode(resp.encoding or "utf-8", errors="ignore")
    except requests.RequestException as exc:
        require_online()  # raises if our own connection is down, so this is retried, not saved
        raise _Unreachable(f"{type(exc).__name__} for {url}") from exc


def _get_json(url: str, body=None):
    resp = _request("POST" if body is not None else "GET", url, json=body)
    resp.raise_for_status()
    return resp.json()
