import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
BATCH_A_WORKFLOW = WORKFLOWS / "update-data-a.yml"
BATCH_B_WORKFLOW = WORKFLOWS / "update-data-b.yml"
DEPLOY_WORKFLOW = WORKFLOWS / "deploy-pages.yml"
LEGACY_WORKFLOW = WORKFLOWS / "update-data.yml"
UPDATER = ROOT / "scripts" / "update_rrg_data.py"


def main():
    a = BATCH_A_WORKFLOW.read_text(encoding="utf-8") if BATCH_A_WORKFLOW.exists() else ""
    b = BATCH_B_WORKFLOW.read_text(encoding="utf-8") if BATCH_B_WORKFLOW.exists() else ""
    deploy = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    updater = UPDATER.read_text(encoding="utf-8")

    require(not LEGACY_WORKFLOW.exists(), "the single sleeping update-data.yml workflow must be removed")

    # Two independent scheduled executions; no runner idles between windows.
    require('cron: "30 22 * * 1-5"' in a, "Batch A must be scheduled at 22:30 UTC on weekdays")
    require('cron: "35 23 * * 1-5"' in b, "Batch B must be scheduled at 23:35 UTC on weekdays")
    for name, text in (("batch A", a), ("batch B", b)):
        require("workflow_dispatch:" in text, f"{name} workflow must support manual runs")
        require("sleep 3660" not in text and "sleep 36" not in text, f"{name} workflow must not idle between request windows")
    require("update_rrg_data.py --provider tiingo --batch A --batch-size 48 --write-phase A" in a, "Batch A must fetch at most 48 symbols and persist its marker")
    require("update_rrg_data.py --provider tiingo --batch B --batch-size 48 --finalize --require-batch-a --write-phase B" in b, "Batch B must fetch the remaining symbols, require Batch A state, and finalize")

    # Batch A never deploys and never finalizes.
    a_before_proof = a.split("coverage-proof:")[0]
    require("deploy-pages" not in a_before_proof and "actions/deploy-pages@v4" not in a_before_proof, "Batch A must not deploy GitHub Pages")
    require("pages: write" not in a_before_proof, "Batch A must not request Pages permissions")
    require("--finalize" not in a_before_proof, "Batch A must not finalize the universe")
    require("github.ref == 'refs/heads/main'" in a_before_proof, "scheduled Batch A must only run on main")
    require("git-auto-commit-action@v5" in a_before_proof, "Batch A must commit its intermediate cache")
    require("file_pattern: public/data/*.json" in a_before_proof, "Batch A must commit the cache and marker together")
    require("github.ref != 'refs/heads/main'" in a.split("coverage-proof:")[1], "coverage proof must not run on main")
    require("deploy-pages" not in a.split("coverage-proof:")[1], "coverage proof must not publish Pages")

    # Batch B proves it consumes the matching Batch A before any request.
    require("TIINGO_API_KEY" in b and "--require-batch-a" in b, "Batch B must contain the verify step and authenticated fetch")
    require(b.index("--require-batch-a") < b.index("TIINGO_API_KEY: ${{ secrets.TIINGO_API_KEY }}"), "Batch B must verify Batch A state before the authenticated fetch step")
    verify_step_at = b.find("--require-batch-a")
    finalize_at = b.find("--finalize")
    deploy_at = b.find("actions/deploy-pages@v4")
    require(verify_step_at != -1 and finalize_at != -1 and deploy_at != -1, "Batch B must contain verify, finalize, and deploy steps")
    require(verify_step_at < finalize_at < deploy_at, "Batch B order must be: verify Batch A, finalize, then deploy")
    require("--validate-only" in b and b.find("--validate-only") < b.find("actions/upload-pages-artifact@v3"), "Batch B must validate the complete universe before uploading")
    require("git-auto-commit-action@v5" in b and "file_pattern: public/data/*.json" in b, "Batch B must commit cache and marker")
    require("concurrency:\n  group: pages" in b, "Batch B must join the pages concurrency group")

    # Deploy workflow publishes only completed phase-B states.
    require("--deploy-gate" in deploy, "deploy workflow must require the phase-B marker gate")
    require(deploy.find("--deploy-gate") < deploy.find("actions/upload-pages-artifact@v3"), "deploy gate must run before the Pages upload")
    require(re.search(r"push:\s+branches:\s+- main", deploy), "deploy workflow must run on pushes to main")
    require("./scripts/prepare-dist.ps1" in deploy, "deploy workflow must prepare dist artifact")
    require("actions/deploy-pages@v4" in deploy, "deploy workflow must deploy to GitHub Pages")

    # Updater mechanics: markers, gates, dedup, caps, real-data-only.
    require("MARKER_PATH = ROOT / \"public\" / \"data\" / \"update-state.json\"" in updater, "updater must define the marker path")
    require("--require-batch-a" in updater and "--ignore-stale-cycle" in updater and "--deploy-gate" in updater and "--write-phase" in updater, "updater must expose marker and gate flags")
    require("require_batch_a_marker" in updater and "require_phase_b_for_deploy" in updater, "updater must implement the batch gates")
    require("--existing-only" not in updater and "--use-existing-on-fail" not in updater, "legacy local-data fallback flags must not exist")
    require("generate_sample_rows" not in updater, "backend synthetic price generation must be removed")
    require("fill_missing_symbols" not in updater, "missing-symbol synthesis must be removed")
    require("market-data.json" not in updater, "legacy market-data.json substitution must be removed")
    require("--batch-size" in updater and "--batch" in updater, "updater must expose batched flags")
    require("MAX_BATCH_SIZE = 48" in updater, "updater must cap each hourly window at 48 requests")
    require("dict.fromkeys(" in updater, "updater must deduplicate shared symbols in definition order")
    require("--ignore-stale-cycle" not in a and "--ignore-stale-cycle" not in b and "--ignore-stale-cycle" not in deploy, "the maintenance override must not be wired into production workflows")

    print("Workflow audit passed: schedules=22:30,23:35UTC batches=48+47 markerGate=require-batch-a deployGate=phaseB idleRunner=false")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
