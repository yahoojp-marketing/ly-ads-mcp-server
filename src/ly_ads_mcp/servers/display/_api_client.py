# Copyright 2026 LY Corporation
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from ads_display_client.api_client import ApiClient as DisplayApiClient
from ads_display_client.configuration import Configuration as DisplayApiConfiguration


@contextmanager
def display_api_client(
    base_url: str,
    access_token: str,
    base_account_id: str | None = None,
) -> Generator[DisplayApiClient, None, None]:
    configuration = DisplayApiConfiguration(host=base_url, access_token=access_token)
    with DisplayApiClient(configuration=configuration) as client:
        if base_account_id is not None:
            client.default_headers["x-z-base-account-id"] = base_account_id
        yield client
