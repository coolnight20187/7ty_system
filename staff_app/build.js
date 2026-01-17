/**
 * 7TY Staff App Build Script
 * Build Android APK for Staff application
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// Configuration
const APP_NAME = '7TY_Staff';
const VERSION = '1.0.0';
const VERSION_CODE = 1;

console.log('='.repeat(50));
console.log(`Building ${APP_NAME} v${VERSION}`);
console.log('='.repeat(50));

// Update version in capacitor.config.json
const configPath = path.join(__dirname, 'capacitor.config.json');
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
config.appName = '7TY Staff';
fs.writeFileSync(configPath, JSON.stringify(config, null, 2));

// Check if android folder exists
const androidPath = path.join(__dirname, 'android');
if (!fs.existsSync(androidPath)) {
    console.log('Adding Android platform...');
    execSync('npx cap add android', { stdio: 'inherit' });
}

// Sync web content
console.log('Syncing web content...');
execSync('npx cap sync android', { stdio: 'inherit' });

// Update version in build.gradle
const gradlePath = path.join(androidPath, 'app', 'build.gradle');
if (fs.existsSync(gradlePath)) {
    let gradleContent = fs.readFileSync(gradlePath, 'utf8');
    
    // Update versionCode
    gradleContent = gradleContent.replace(
        /versionCode \d+/,
        `versionCode ${VERSION_CODE}`
    );
    
    // Update versionName
    gradleContent = gradleContent.replace(
        /versionName "[^"]+"/,
        `versionName "${VERSION}"`
    );
    
    fs.writeFileSync(gradlePath, gradleContent);
    console.log(`Updated version to ${VERSION} (code: ${VERSION_CODE})`);
}

// Build APK
console.log('Building release APK...');
try {
    execSync('cd android && ./gradlew assembleRelease', { 
        stdio: 'inherit',
        env: { ...process.env, JAVA_HOME: process.env.JAVA_HOME || '/usr/lib/jvm/java-17-openjdk-amd64' }
    });
    
    // Find and copy APK
    const apkDir = path.join(androidPath, 'app', 'build', 'outputs', 'apk', 'release');
    const apkFiles = fs.readdirSync(apkDir).filter(f => f.endsWith('.apk'));
    
    if (apkFiles.length > 0) {
        const srcApk = path.join(apkDir, apkFiles[0]);
        const destApk = path.join(__dirname, '..', 'downloads', `${APP_NAME}_v${VERSION}.apk`);
        
        fs.mkdirSync(path.dirname(destApk), { recursive: true });
        fs.copyFileSync(srcApk, destApk);
        
        console.log('='.repeat(50));
        console.log(`✅ Build successful!`);
        console.log(`📦 APK: ${destApk}`);
        console.log('='.repeat(50));
    }
} catch (error) {
    console.error('Build failed:', error.message);
    process.exit(1);
}
