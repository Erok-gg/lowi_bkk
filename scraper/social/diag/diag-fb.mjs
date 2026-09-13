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

await page.screenshot({ path: "diag-screenshot.png", fullPage: false });

const info = await page.evaluate(() => {
  const bodyText = document.body.innerText.slice(0, 3000);
  const feed = document.querySelectorAll('div[role="feed"] > div');
  const articles = document.querySelectorAll('div[role="article"]');
  const target = feed[2] || feed[0] || articles[0];
  return {
    title: document.title,
    url: location.href,
    feedCount: feed.length,
    articleCount: articles.length,
    targetHTML: target ? target.outerHTML.slice(0, 3000) : null,
    targetText: target ? target.innerText.slice(0, 800) : null,
    bodyTextSample: bodyText,
  };
});
writeFileSync("diag-fb.json", JSON.stringify(info, null, 2));
console.log("done:", url);
await page.close();
process.exit(0);
