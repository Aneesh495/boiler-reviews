const path = require('path');

module.exports = {
  testDir: './e2e',
  timeout: 30000,
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    headless: true,
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH || path.join(process.env.HOME, 'Library/Caches/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell'),
      args: ['--no-sandbox'],
    },
  },
  webServer: {
    command: 'python3 -m http.server 4173 --directory build',
    port: 4173,
    reuseExistingServer: false,
    timeout: 30000,
  },
};
