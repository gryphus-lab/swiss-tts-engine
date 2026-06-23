// metro.config.js
const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// Disable the package exports resolution that often conflicts with Node 20+
config.resolver.unstable_enablePackageExports = false;

module.exports = config;