import json

from src.signals import careers_page as cp


def ld(*postings):
    return '<script type="application/ld+json">' + json.dumps({"@graph": list(postings)}) + "</script>"


def test_json_ld_postings_found_when_nested():
    html = ld({"@type": "JobPosting", "title": "Scheduler",
               "jobLocation": {"address": {"addressLocality": "Brooklyn", "addressRegion": "NY"}}},
              {"@type": "Organization", "name": "x"})
    assert cp._json_ld_postings(html) == [{"title": "Scheduler", "location": "Brooklyn, NY"}]


def test_json_ld_ignores_bad_json_and_untitled_postings():
    html = '<script type="application/ld+json">{not json</script>' + ld({"@type": "JobPosting"})
    assert cp._json_ld_postings(html) == []


def test_in_area_rules():
    acc = {"state": "NY", "city": "Brooklyn"}
    assert cp._in_area("", acc)  # no location given counts as local
    assert cp._in_area("Albany, NY", acc)
    assert cp._in_area("Remote - New York", acc)
    assert cp._in_area("Brooklyn office", acc)
    assert not cp._in_area("Newark, NJ", acc)


def test_detect_ats_by_embed_domain():
    assert cp._detect_ats('<iframe src="https://x.applytojob.com/apply">') == "JazzHR"
    assert cp._detect_ats("<p>no system here</p>") is None


def test_career_links_same_site_only_best_first():
    html = """
      <a href="/careers">Careers</a>
      <a href="/about/join-us/openings">Openings</a>
      <a href="https://elsewhere.example/jobs">Jobs</a>
      <a href="mailto:jobs@site.example">Email</a>
      <a href="/careers/form.pdf">Form</a>
    """
    links = cp._career_links("https://www.site.example/", html, "site.example", set())
    assert links[0] == "https://www.site.example/careers"
    assert all("elsewhere" not in l and not l.endswith(".pdf") for l in links)


def test_read_feed_lever(monkeypatch):
    monkeypatch.setattr(cp, "_get_json", lambda url, body=None: [
        {"text": "Scheduler", "categories": {"location": "Brooklyn, NY"}},
        {"text": "Analyst", "categories": {}},
    ])
    ats, postings, total = cp._read_feed('<a href="https://jobs.lever.co/bluebird">jobs</a>')
    assert ats == "Lever" and total == 2 and postings[1]["location"] == ""


def test_fetch_without_website_is_not_checked():
    out = cp.fetch({"website": ""}, {"role_keywords": {"ops": ["scheduler"]}})
    assert out["jobs_status"] == "no_website" and out["jobs_total"] is None and out["jobs_ops"] is None


def test_fetch_counts_local_postings_into_buckets(monkeypatch):
    site = {"status": "counted", "ats": "Lever", "source_url": "https://site.example/careers", "total": 3,
            "postings": [{"title": "Scheduler", "location": "Brooklyn, NY"},
                         {"title": "Billing Specialist", "location": "NY"},
                         {"title": "Scheduler", "location": "Newark, NJ"}]}
    monkeypatch.setattr(cp, "_crawl_cached", lambda url: site)
    out = cp.fetch({"website": "site.example", "state": "NY", "city": "Brooklyn"},
                   {"role_keywords": {"ops": ["scheduler"], "admin": ["billing"]}})
    assert out["jobs_total"] == 2 and out["jobs_total_all_locations"] == 3
    assert out["jobs_ops"] == 1 and out["jobs_admin"] == 1


def test_unreadable_site_reports_status_not_zero(monkeypatch):
    monkeypatch.setattr(cp, "_crawl_cached", lambda url: {"status": "site_unreachable", "ats": None,
                                                          "source_url": None, "postings": [], "total": None})
    out = cp.fetch({"website": "site.example"}, {"role_keywords": {}})
    assert out["jobs_status"] == "site_unreachable" and out["jobs_total"] is None
