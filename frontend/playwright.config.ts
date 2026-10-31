import { defineConfig } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
const runtime = mkdtempSync(join(tmpdir(), "resourcing-ui-"));
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  timeout: 30000,
  use: { baseURL: "http://127.0.0.1:8017", trace: "retain-on-failure" },
  webServer: {
    command:
      "../.venv/bin/python -m uvicorn tests.process_app:create_app --factory --app-dir .. --host 127.0.0.1 --port 8017",
    env: { TEST_RUNTIME: runtime },
    url: "http://127.0.0.1:8017/health",
    reuseExistingServer: false,
    timeout: 20000,
  },
});
