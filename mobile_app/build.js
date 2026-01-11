const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

// Configuration
const API_BASE_URL = process.env.API_URL || 'https://7ty.vn';
const SOURCE_FILE = '../static/agent_app.html';
const OUTPUT_DIR = './www';

console.log('🚀 Building 7TY Agent Mobile App...\n');

// Create output directory
if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

// Read source file
let html = fs.readFileSync(path.join(__dirname, SOURCE_FILE), 'utf8');

// Update API base URL for production
html = html.replace(
    /const API_BASE_URL = ['"][^'"]*['"]/g,
    `const API_BASE_URL = '${API_BASE_URL}/api'`
);

// Add Capacitor plugins initialization
const capacitorInit = `
    <script src="https://unpkg.com/@nicepayments/nicepay-capacitor-plugin@latest/dist/plugin.js"></script>
    <script>
        // Initialize Capacitor plugins
        document.addEventListener('DOMContentLoaded', async () => {
            if (window.Capacitor) {
                const { SplashScreen } = await import('@capacitor/splash-screen');
                const { StatusBar, Style } = await import('@capacitor/status-bar');
                const { App } = await import('@capacitor/app');
                
                // Hide splash screen after load
                SplashScreen.hide();
                
                // Set status bar style
                StatusBar.setStyle({ style: Style.Dark });
                StatusBar.setBackgroundColor({ color: '#0d4a4a' });
                
                // Handle back button on Android
                App.addListener('backButton', ({ canGoBack }) => {
                    if (canGoBack) {
                        window.history.back();
                    } else {
                        App.exitApp();
                    }
                });
                
                console.log('Capacitor initialized');
            }
        });
    </script>
`;

// Insert Capacitor script before closing body tag
html = html.replace('</body>', capacitorInit + '</body>');

// Write output file
fs.writeFileSync(path.join(OUTPUT_DIR, 'index.html'), html);

// Copy manifest
const manifest = {
    "name": "7TY Agent",
    "short_name": "7TY Agent",
    "start_url": "./index.html",
    "display": "standalone",
    "background_color": "#f5f7fb",
    "theme_color": "#0d4a4a",
    "icons": [
        {
            "src": "icons/icon-192.png",
            "sizes": "192x192",
            "type": "image/png"
        },
        {
            "src": "icons/icon-512.png",
            "sizes": "512x512",
            "type": "image/png"
        }
    ]
};

fs.writeFileSync(
    path.join(OUTPUT_DIR, 'manifest.json'),
    JSON.stringify(manifest, null, 2)
);

// Create icons directory
const iconsDir = path.join(OUTPUT_DIR, 'icons');
if (!fs.existsSync(iconsDir)) {
    fs.mkdirSync(iconsDir, { recursive: true });
}

console.log('✅ Build completed!');
console.log(`📁 Output: ${path.resolve(OUTPUT_DIR)}`);
console.log('\n📱 Next steps:');
console.log('   1. npm run cap:sync');
console.log('   2. npm run cap:open:android  (for Android)');
console.log('   3. npm run cap:open:ios      (for iOS)');
