import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[1]
UPDATE_WORKFLOW = ROOT / ".github" / "workflows" / "update-data.yml"
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-pages.yml"
UPDATER = ROOT / "scripts" / "update_rrg_data.py"


def main():
    update = UPDATE_WORKFLOW.read_text(encoding="utf-8")
    deploy = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    updater = UPDATER.read_text(encoding="utf-8")

    require('cron: "30 22 * * 1-5"' in update, "RRG data update workflow must run after U.S. market close")
    require("workflow_dispatch:" in update, "RRG data update workflow must support manual runs")
    require("contents: write" in update, "RRG data update workflow must be allowed to commit data")
    require("pages: write" in update and "id-token: write" in update, "RRG data update workflow must have Pages deploy permissions")
    require("TIINGO_API_KEY: ${{ secrets.TIINGO_API_KEY }}" in update, "RRG data update workflow must expose TIINGO_API_KEY secret")
    require("git-auto-commit-action@v5" in update, "RRG data update workflow must commit updated data")
    require("file_pattern: public/data/rrg.json" in update, "RRG data update workflow must only commit generated data")
    require("./scripts/prepare-dist.ps1" in update, "RRG data update workflow must prepare dist artifact after data generation")
    require("actions/upload-pages-artifact@v3" in update and "path: dist" in update, "RRG data update workflow must upload dist")
    require("actions/deploy-pages@v4" in update, "RRG data update workflow must deploy fresh data to GitHub Pages")

    # Two-batch production schedule within Tiingo Starter's hourly window.
    require("update_rrg_data.py --provider tiingo --batch A --batch-size 48" in update, "batch A must fetch at most 48 symbols")
    require("update_rrg_data.py --provider tiingo --batch B --batch-size 48 --finalize" in update, "batch B must fetch the remaining symbols and finalize")
    require("sleep 3660" in update, "batch B must start in a later Tiingo hourly window")
    require("update_rrg_data.py --validate-only" in update, "a complete-universe validation must run before deployment")
    batch_a_at = update.find("--batch A")
    first_deploy_at = update.find("actions/deploy-pages@v4")
    batch_b_commit_at = update.find("Update generated RRG data\n", update.find("--batch B"))
    require(batch_a_at != -1 and first_deploy_at != -1 and batch_a_at < first_deploy_at, "batch A must run before any deployment")
    require(batch_b_commit_at != -1 and batch_b_commit_at < first_deploy_at, "batch B must commit before the deployment step")

    # Coverage proof never publishes and never runs on main.
    proof_at = update.find("coverage-proof:")
    require(proof_at != -1, "branch-only coverage proof job must remain defined")
    proof_block = update[proof_at:]
    require("github.ref != 'refs/heads/main'" in proof_block, "coverage proof must not run on main")
    require("deploy-pages" not in proof_block and "pages: write" not in proof_block, "coverage proof must not publish Pages")
    require("if: github.ref == 'refs/heads/main'" in update.split("coverage-proof:")[0], "the production update job must only run on main")

    require("workflow_dispatch:" in deploy, "deploy workflow must support manual runs")
    require(re.search(r"push:\s+branches:\s+- main", deploy), "deploy workflow must run on pushes to main")
    require("pages: write" in deploy and "id-token: write" in deploy, "deploy workflow must have Pages permissions")
    require("update_rrg_data.py --validate-only" in deploy, "deploy workflow must gate publication on the complete real-data universe")
    validate_at = deploy.find("--validate-only")
    upload_at = deploy.find("actions/upload-pages-artifact@v3")
    require(validate_at != -1 and upload_at != -1 and validate_at < upload_at, "validation must run before the Pages artifact upload")
    require("./scripts/prepare-dist.ps1" in deploy, "deploy workflow must prepare dist artifact")
    require("actions/deploy-pages@v4" in deploy, "deploy workflow must deploy to GitHub Pages")

    # Production updater must be real-data-only.
    require("--existing-only" not in updater and "--use-existing-on-fail" not in updater, "legacy local-data fallback flags must not exist")
    require("generate_sample_rows" not in updater, "backend synthetic price generation must be removed")
    require("fill_missing_symbols" not in updater, "missing-symbol synthesis must be removed")
    require("market-data.json" not in updater, "legacy market-data.json substitution must be removed")
    require("--finalize" in updater and "--batch-size" in updater and "--batch" in updater, "updater must expose batched finalize flags")
    require("MAX_BATCH_SIZE = 48" in updater, "updater must cap each hourly window at 48 requests")
    require("dict.fromkeys(" in updater, "updater must deduplicate shared symbols in definition order")

    print("Workflow audit passed: batches=A,B cap=48/window finalizeGate=true branchProofOnly=true")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
