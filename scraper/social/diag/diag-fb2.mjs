import { connectToChrome, humanDelay, humanScroll } from "./utils/browser.js";
import { writeFileSync } from "fs";

const { browser, context } = await connectToChrome();
const page = await context.newPage();
page.on("dialog", (d) => d.dismiss().catch(() => {}));

const url = process.argv[2] || "https://www.facebook.com/groups/bangkokcondoforsalerent/";
await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
await humanDelay(page, 3000, 4000);
await humanScroll(page, 3);
await humanDelay(page, 2000, 3000);

const info = await page.evaluate(() => {
  const feed = document.querySelectorAll('div[role="feed"] > div');
  const results = [];
  for (let i = 0; i < feed.length; i++) {
    const el = feed[i];
    const text = el.innerText || "";
    if (!/RENT|SALE|ขาย|เช่า|SQ\.M|ตร\.ม|condo|SALADAENG/i.test(text)) continue;
    const links = [...el.querySelectorAll("a")].map((a) => ({
      href: a.getAttribute("href"),
      role: a.getAttribute("role"),
      ariaLabel: a.getAttribute("aria-label"),
      text: (a.textContent || "").trim().slice(0, 30),
    }));
    const abbrs = [...el.querySelectorAll("abbr")].map((a) => ({
      utime: a.getAttribute("data-utime"),
      text: (a.textContent || "").trim(),
    }));
    const spansWithAria = [...el.querySelectorAll("span[aria-label], a[aria-label]")].map((s) => s.getAttribute("aria-label"));
    results.push({ index: i, textSample: text.slice(0, 200), linkCount: links.length, links: links.slice(0, 15), abbrs, spansWithAria: spansWithAria.slice(0, 10) });
  }
  return results;
});
writeFileSync("diag-fb2.json", JSON.stringify(info, null, 2));
console.log("done, matches:", info.length);
await page.close();
process.exit(0);
