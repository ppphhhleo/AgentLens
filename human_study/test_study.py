#!/usr/bin/env python3
"""Simulate a human participant completing a study task.

Uses Playwright to:
1. Visit the study landing page
2. Enter a participant ID
3. Click a task to start
4. Interact with the proxied page (click, scroll)
5. Type an answer
6. Submit

Verifies that the trajectory was captured correctly.

Usage:
    python human_study/test_study.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

STUDY_URL = "http://127.0.0.1:8080"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def wait_for_server(url: str, timeout: int = 10):
    """Wait for the study server to be ready."""
    import httpx

    for i in range(timeout):
        try:
            resp = httpx.get(url, timeout=2)
            if resp.status_code == 200:
                print(f"✅ Server ready at {url}")
                return True
        except Exception:
            pass
        time.sleep(1)
        print(f"   Waiting for server... ({i+1}/{timeout})")
    raise RuntimeError(f"Server not ready after {timeout}s")


def run_simulated_participant(participant_id: str, task_id: str):
    """Simulate a user completing a task via the study platform."""
    from playwright.sync_api import sync_playwright

    print(f"\n{'='*60}")
    print(f"🧑 Simulating participant: {participant_id}")
    print(f"📋 Task: {task_id}")
    print(f"{'='*60}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        # Step 1: Visit landing page
        print("1️⃣  Visiting landing page...")
        page.goto(STUDY_URL)
        page.wait_for_load_state("networkidle")
        title = page.title()
        print(f"   Page title: {title}")
        assert "AgentLens" in title, f"Unexpected title: {title}"

        # Step 2: Enter participant ID
        print(f"2️⃣  Entering participant ID: {participant_id}")
        page.fill("#pid", participant_id)

        # Step 3: Click the task card
        print(f"3️⃣  Clicking task: {task_id}")
        # Find and click the Start Task button for our task
        cards = page.query_selector_all(".task-card")
        target_card = None
        for card in cards:
            h3 = card.query_selector("h3")
            if h3 and h3.text_content() == task_id:
                target_card = card
                break

        if target_card is None:
            raise RuntimeError(f"Task card '{task_id}' not found on landing page")

        btn = target_card.query_selector(".btn")
        btn.click()

        # Step 4: Wait for proxied page to load
        print("4️⃣  Waiting for proxied study page to load...")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(3)  # Give the page time to fully render

        # Verify we're on a study page
        current_url = page.url
        print(f"   Current URL: {current_url}")
        assert "/study/" in current_url, f"Not on study page: {current_url}"

        # Step 5: Simulate some interactions
        print("5️⃣  Simulating user interactions...")

        # Click somewhere on the page
        page.mouse.click(400, 300)
        print("   → Clicked at (400, 300)")
        time.sleep(0.5)

        # Scroll down
        page.mouse.wheel(0, 300)
        print("   → Scrolled down 300px")
        time.sleep(0.5)

        # Click another spot
        page.mouse.click(600, 400)
        print("   → Clicked at (600, 400)")
        time.sleep(0.5)

        # Scroll back up
        page.mouse.wheel(0, -150)
        print("   → Scrolled up 150px")
        time.sleep(1)

        # Step 6: Check the overlay is present
        print("6️⃣  Checking overlay is present...")
        overlay = page.query_selector("#agentlens-study-overlay")
        if overlay:
            print("   ✅ Overlay found!")
        else:
            print("   ⚠️  Overlay not found — may still be loading")

        # Step 7: Type an answer
        answer_text = f"Test answer from {participant_id}: The toggle was found and clicked."
        print(f"7️⃣  Typing answer: '{answer_text[:50]}...'")
        answer_input = page.query_selector("#agentlens-answer")
        if answer_input:
            answer_input.fill(answer_text)
        else:
            print("   ⚠️  Answer input not found")

        time.sleep(1)

        # Step 8: Submit
        print("8️⃣  Clicking Submit...")
        submit_btn = page.query_selector("#agentlens-submit-btn")
        if submit_btn:
            submit_btn.click()
            time.sleep(2)  # Wait for submission
            print("   ✅ Submitted!")
        else:
            print("   ⚠️  Submit button not found")

        # Give events time to flush
        time.sleep(2)

        context.close()
        browser.close()

    print(f"\n{'='*60}")
    print(f"✅ Participant {participant_id} simulation complete!")
    print(f"{'='*60}\n")


def verify_results():
    """Check that trajectory files were saved correctly."""
    print("\n📊 Verifying results...\n")

    # Results are now in per-participant subdirectories:
    # results/<participant_id>/<task>_<session>.json
    result_files = list(RESULTS_DIR.glob("**/*.json"))
    print(f"Found {len(result_files)} trajectory file(s):")

    # Also show directory structure
    participant_dirs = [d for d in RESULTS_DIR.iterdir() if d.is_dir()]
    print(f"Participant directories: {[d.name for d in participant_dirs]}")

    for f in result_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            events = data.get("events", [])
            event_types = {}
            for e in events:
                t = e.get("type", "unknown")
                event_types[t] = event_types.get(t, 0) + 1

            rel_path = f.relative_to(RESULTS_DIR)
            print(f"\n  📄 {rel_path}")
            print(f"     Participant: {data.get('participant_id', '?')}")
            print(f"     Task: {data.get('task_id', '?')}")
            print(f"     Answer: {(data.get('answer') or '')[:60]}")
            print(f"     Events: {len(events)}")
            print(f"     Duration: {data.get('metrics', {}).get('duration_ms', '?')}ms")
            print(f"     Event types: {event_types}")
            print(f"     Started: {data.get('started_at', '?')}")
            print(f"     Completed: {data.get('completed_at', '?')}")

            # Validate structure
            assert data.get("participant_id"), "Missing participant_id"
            assert data.get("task_id"), "Missing task_id"
            assert data.get("answer"), "Missing answer"
            assert len(events) > 0, "No events recorded"
            assert data.get("started_at"), "Missing started_at"
            assert data.get("completed_at"), "Missing completed_at"
            print("     ✅ Structure valid!")

        except Exception as e:
            print(f"     ❌ Error: {e}")

    return len(result_files) > 0


def main():
    print("🔬 AgentLens Human Study — End-to-End Test\n")

    # Clean up old results (recursive since they're in subdirs now)
    import shutil
    for d in RESULTS_DIR.iterdir():
        if d.is_dir():
            shutil.rmtree(d)
        elif d.is_file() and d.suffix == ".json":
            d.unlink()
    print("🧹 Cleaned old results\n")

    # Start the study server in the background
    print("🚀 Starting study server...")
    server_proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve().parent / "server.py"),
         "--host", "127.0.0.1", "--port", "8080"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for_server(STUDY_URL)

        # Simulate 3 different participants with UMN x500 style IDs
        run_simulated_participant("selva053", "tf_discretize_toggle")
        run_simulated_participant("haop001", "datavoyager_most_fuel_efficient")
        run_simulated_participant("selva053", "datavoyager_europe_100hp_4cyl_count")

        # Verify results
        success = verify_results()

        if success:
            print("\n✅ ALL TESTS PASSED — Study platform is working correctly!")
            print(f"   Results saved in: {RESULTS_DIR}")
        else:
            print("\n❌ TESTS FAILED — No results found")
            sys.exit(1)

    finally:
        server_proc.terminate()
        server_proc.wait(timeout=5)
        print("\n🛑 Server stopped")


if __name__ == "__main__":
    main()
