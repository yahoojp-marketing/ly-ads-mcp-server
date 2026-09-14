# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from ads_search_client.api_client import ApiClient as SearchApiClient
from ads_search_client.configuration import Configuration as SearchApiConfiguration


@contextmanager
def search_api_client(
    base_url: str,
    access_token: str,
    base_account_id: str | None = None,
) -> Generator[SearchApiClient, None, None]:
    configuration = SearchApiConfiguration(host=base_url, access_token=access_token)
    with SearchApiClient(configuration=configuration) as client:
        if base_account_id is not None:
            client.default_headers["x-z-base-account-id"] = base_account_id
        yield client
