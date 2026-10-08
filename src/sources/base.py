import pandas as pd

SCHEMA = ["name", "address", "city", "state", "zip", "phone", "website", "source", "license_type", "entity_id"]


def empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=SCHEMA)
