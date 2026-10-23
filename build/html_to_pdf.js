// Print an HTML page to PDF (and a PNG preview) with Chromium.
//   node build/html_to_pdf.js page.html out.pdf [preview.png]
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const [src, out, png] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 816, height: 1056 } });
  await page.goto('file://' + path.resolve(src));
  await page.pdf({ path: out, format: 'Letter', printBackground: true, preferCSSPageSize: true });
  if (png) await page.screenshot({ path: png, fullPage: true });
  await browser.close();
  console.log('wrote', out);
})();
