# LY Ads MCP Server

[日本語](README.ja.md)

LY Ads MCP Server is a local server for accessing the [LY Ads API](https://ads-developers.yahoo.co.jp/en/ads-api/) through the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).
It enables MCP-compatible AI agents to access information about Display Ads and Search Ads accounts, campaigns, ads, and more.

LY Ads is an advertising service designed for advertisers in Japan.

The server uses Streamable HTTP and [FastMCP OAuth Proxy](https://gofastmcp.com/servers/auth/oauth-proxy) for LY Ads OAuth authentication.

## Available tools

### Display Ads

| Tool | Description |
|---|---|
| `list_accessible_display_base_accounts` | Retrieves base accounts available to the authorized user. |
| `list_accessible_display_accounts` | Retrieves ad accounts under a base account. |
| `list_display_campaigns` | Retrieves campaigns for an ad account. |
| `list_display_labels` | Retrieves labels for an ad account. |
| `list_display_ad_groups` | Retrieves ad groups for an ad account. |
| `list_display_ad_group_targets` | Retrieves targeting settings for ad groups. |
| `list_display_ads` | Retrieves ads for an ad account. |
| `get_display_report_fields` | Retrieves the fields available for a report type. |
| `read_display_report` | Creates a report using the specified conditions and returns a preview of the first 50 rows and the location of the full CSV file. |

### Search Ads

| Tool | Description |
|---|---|
| `list_accessible_search_base_accounts` | Retrieves base accounts available to the authorized user. |
| `list_accessible_search_accounts` | Retrieves ad accounts under a base account. |
| `list_search_campaigns` | Retrieves campaigns for an ad account. |
| `list_search_labels` | Retrieves labels for an ad account. |
| `list_search_campaign_targets` | Retrieves targeting settings for campaigns. |
| `list_search_campaign_negative_keywords` | Retrieves negative keywords configured for campaigns. |
| `list_search_ad_groups` | Retrieves ad groups for an ad account. |
| `list_search_ad_group_keywords` | Retrieves keywords configured for ad groups. |
| `list_search_ads` | Retrieves ads for an ad account. |
| `get_search_report_fields` | Retrieves the fields available for a report type. |
| `read_search_report` | Creates a report using the specified conditions and returns a preview of the first 50 rows and the location of the full CSV file. |

Display Ads tools are exposed to MCP clients under the `ly_ads_display` namespace, and Search Ads tools are exposed under the `ly_ads_search` namespace.
All `list_*` tools return one page of results at a time.

### Notes on using `read_display_report` and `read_search_report`

When requesting a report, specify the ad type, target account, date range, metrics, and dimensions you want to analyze.
You do not need to look up or specify API field names.
The AI agent checks the fields available for the report type and selects a combination based on the field metadata returned by the API.

```text
For Search Ads base account ID 123456 and account ID 789012,
retrieve clicks, conversions, and cost by campaign for August 2026.
```

Some Display Ads report types—such as reach, conversion path, cross-campaign reach, and attribution model comparison reports—require additional report-specific parameters.
If the request does not provide enough information to determine those conditions, the AI agent asks for the required details.
Date-range requirements also vary by Search Ads report type.

The result includes a preview of the first 50 rows.
The full report, including rows omitted from the preview, is saved as a UTF-8 CSV file under
`display/YYYY-MM-DD` or `search/YYYY-MM-DD` in the directory specified by `LY_ADS_REPORT_OUTPUT_DIR`.
The returned path is a local file path on the machine running the server, not an MCP Resource.
The MCP client must have permission to read the path, and remote or sandboxed clients may not be able to access the file.
CSV files are not deleted automatically.

An error is returned if the report is not completed within 60 seconds.
If that happens, narrow the date range, fields, or filters and request the report again.

## Before you begin

Before using the server, you must apply for access to the LY Ads API and issue an OAuth client for MCP.

1. Follow the [LY Ads API application instructions](https://ads-developers.yahoo.co.jp/en/ads-api/startup-guide/apply-api-use.html) to apply for API access.
2. After completing the application process, open the [MCP OAuth client issuance page for Business ID](https://connect-business.yahoo.co.jp/client/mcp).
3. Issue an OAuth client for MCP.
4. Obtain the issued client ID and client secret.
    * Standard API applications are managed at the company level, while OAuth clients for MCP are managed at the Business ID level.

The server uses the OAuth client credentials when it starts.
FastMCP OAuth Proxy manages the access token and refresh token, so you do not need to configure them directly in the MCP client.

You need Administrator Permission or User Permission for the API Management Tool to open the MCP OAuth client issuance page.
For details on managing access to the API Management Tool, see the following help page.

* [How can I add an administrator access for LY Ads API? - LY Ads API | Developer Center](https://ads-developers.yahoo.co.jp/en/ads-api/faq/faq_en.html)

## Setup

Install Python 3.11 or later, [pipx](https://pipx.pypa.io/stable/installation/), and Git.

Set the OAuth client credentials and JWT signing key as environment variables in the shell where you will run the server.

```bash
export LY_ADS_CLIENT_ID="ISSUED_CLIENT_ID"
export LY_ADS_CLIENT_SECRET="ISSUED_CLIENT_SECRET"
export LY_ADS_MCP_JWT_SIGNING_KEY="GENERATED_JWT_SIGNING_KEY"
export LY_ADS_REPORT_OUTPUT_DIR="$HOME/.ly-ads-mcp/reports"
```

Do not store these values in files tracked by Git, and ensure that other users cannot read them.

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `LY_ADS_CLIENT_ID` | Yes | Client ID of the OAuth client for MCP. |
| `LY_ADS_CLIENT_SECRET` | Yes | Client secret of the OAuth client for MCP. |
| `LY_ADS_MCP_JWT_SIGNING_KEY` | Yes | Signing key for JWTs issued by FastMCP. Set this to a random value different from the OAuth client secret. |
| `LY_ADS_REPORT_OUTPUT_DIR` | No | Directory where report CSV files are saved. Defaults to `reports` under the directory from which the server is started. |

### Generate a JWT signing key

Generate the JWT signing key separately from the OAuth client secret.
Do not reuse the same value.
The following command generates a random 256-bit value.

```bash
openssl rand -base64 32
```

Set the generated value as `LY_ADS_MCP_JWT_SIGNING_KEY`.
The value must contain at least 32 characters.
Because length alone does not ensure sufficient randomness, use a cryptographically secure random number generator such as the command above.

## Start the server

Run a specific version of the server with the following command.

```bash
pipx run \
  --spec "git+https://github.com/yahoojp-marketing/ly-ads-mcp-server.git@v0.0.1" \
  ly-ads-mcp
```

The server accepts MCP client connections at `http://localhost:18765/mcp`.

## Configure an MCP client

Configuration formats vary by MCP client.
The following example is for clients that support the `mcpServers` format.

```json
{
  "mcpServers": {
    "ly-ads-mcp": {
      "type": "http",
      "url": "http://localhost:18765/mcp"
    }
  }
}
```

After configuring the client, connect to the server and authorize access using your Business ID on
the authorization page displayed in your browser. Configuration fields and OAuth authorization procedures vary by
client, so refer to your MCP client's documentation.

## Usage examples

After connecting to the server and completing OAuth authorization, you can send requests like the following from your MCP client.

```text
Show me the Display Ads accounts I can access.
```

```text
Retrieve the Search Ads campaigns for account ID 1234567890.
```

```text
Show me the campaign-level negative keywords configured for Search Ads account ID 1234567890.
```

Most tools use a base account ID (`baseAccountId`) and an ad account ID (`accountId`).
If you do not know these IDs, first ask the agent to retrieve the available base accounts and ad accounts.

## Generated API clients

The `ads_display_client` and `ads_search_client` packages included under `generated/` were generated with OpenAPI Generator 7.13.0 using the following options.

```text
-g python
--additional-properties=packageName=<PACKAGE_NAME>,projectName=<PROJECT_NAME>,packageVersion=<PACKAGE_VERSION>
--global-property apiDocs=false,apiTests=false,modelDocs=false,modelTests=false
--skip-validate-spec
```

## Data and credential handling

Data retrieved from LY Ads through the LY Ads MCP Server is provided to the AI agent via the MCP client.
Use the server only with trusted MCP clients, and review each client's data-handling terms.

This MCP server listens only on `localhost`.
Do not include client secrets, access tokens, or refresh tokens in prompts.
