/**
 * Typed API client. T-001 ships the type surface only; concrete fetchers land in T-006
 * (chat) and T-002–T-005 (admin/ingestion). Generated zod validators land in `lib/schemas/`
 * when the openapi → zod codegen lands.
 *
 * See: docs/api/openapi.yaml, docs/contracts/code-gen-guide.md §5.
 */

export type ApiBaseUrl = string;

export interface ApiClient {
  baseUrl: ApiBaseUrl;
}

export function createApiClient(baseUrl: ApiBaseUrl): ApiClient {
  return { baseUrl };
}
