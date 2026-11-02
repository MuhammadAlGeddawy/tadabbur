"""Headless test of the demo page with a mocked Claude `sample` capability.

The mock returns plausible JSON so the full pipeline path (understand -> retrieve -> rank -> guard -> render)
runs in a real browser. It also injects a Quran quote and an unknown ID to prove the guard works.
"""
import json
import os
import subprocess
import sys
import time
from playwright.sync_api import sync_playwright

SITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")
_page = open(SITE + "/index.html", encoding="utf-8").read()
open(SITE + "/_test.html", "w", encoding="utf-8").write("<!doctype html><html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"></head><body>" + _page + "</body></html>")
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp"
srv = subprocess.Popen([sys.executable, "-m", "http.server", "8765", "--bind", "127.0.0.1"], cwd=SITE,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)

MOCK = r"""
window.__calls = [];
window.claude = { use: async (name) => {
  if (name !== "sample") return null;
  const f = async (input) => ({ text: "" });
  f.json = async (input, opts) => {
    window.__calls.push({ tier: opts && opts.modelTier, len: input.length });
    if (input.includes("query-understanding")) return {
      language: "egyptian", intent: "concept",
      msa: "كيف أصبر عندما يبتليني الله بأمر صعب",
      classical: ["الصبر على البلاء والمصائب", "الاستعانة بالصبر والصلاة عند الشدائد"], english: "patience in hardship" };
    const ids = [...input.matchAll(/^\[(\d+:\d+)\]/gm)].map(m => m[1]);
    return { no_answer: false, results: [
      { id: ids[0], grade: 3, why: "تحث الآية المؤمنين على الصبر عند المصائب وتبشر الصابرين بالأجر." },
      { id: ids[1], grade: 2, why: "قال تعالى يا أيها الذين آمنوا استعينوا بالصبر والصلاة إن الله مع الصابرين" },
      { id: "999:1", grade: 3, why: "fake id" },
      { id: ids[2], grade: 1, why: "ترتبط الآية بالموضوع لأنها تذكر جزاء الصابرين." } ] };
  };
  return f;
} };
"""

with sync_playwright() as p:
    b = p.chromium.launch()
    errors = []
    for scheme in ("light", "dark"):
        pg = b.new_page(viewport={"width": 1280, "height": 1600}, color_scheme=scheme)
        pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
        pg.on("pageerror", lambda e: errors.append(str(e)))
        if scheme == "light":
            pg.add_init_script(MOCK)
        pg.goto("http://127.0.0.1:8765/_test.html")
        pg.wait_for_function("document.querySelectorAll('.card').length > 0", timeout=30000)
        print(scheme, "preview cards:", pg.locator(".card").count(), "| status:", pg.locator("#status").inner_text()[:90])
        if scheme == "light":
            pg.fill("#q", "إزاي أصبر لما ربنا يبتليني بحاجة صعبة؟")
            pg.click("#go")
            pg.wait_for_function("document.querySelector('#status').textContent === 'Done.'", timeout=30000)
            print("pipeline cards:", pg.locator(".card").count(), "| guarded:", pg.locator(".guarded").count(),
                  "| guard kv:", pg.locator("#kv-guard").inner_text(), "| calls:", pg.evaluate("window.__calls"))
            print("understand kv:", pg.locator("#kv-understand").inner_text().replace("\n", " / "))
            pg.screenshot(path=f"{OUT}/demo_search_light.png", full_page=False)
            pg.goto("http://127.0.0.1:8765/_test.html#benchmark")
            pg.wait_for_timeout(2500)
            pg.click("#bBase")
            pg.wait_for_timeout(1500)
            print("benchmark stats:", pg.locator("#bStats").inner_text().replace("\n", " "))
            pg.screenshot(path=f"{OUT}/demo_bench_light.png", full_page=False)
        else:
            pg.screenshot(path=f"{OUT}/demo_preview_dark.png", full_page=False)
        mp = b.new_page(viewport={"width": 390, "height": 900}, color_scheme=scheme)
        mp.goto("http://127.0.0.1:8765/_test.html")
        mp.wait_for_function("document.querySelectorAll('.card').length > 0", timeout=30000)
        ow = mp.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        print(scheme, "mobile horizontal overflow:", ow)
        if scheme == "light":
            mp.screenshot(path=f"{OUT}/demo_mobile.png")
    print("console errors:", errors[:5])
    b.close()
srv.terminate()
