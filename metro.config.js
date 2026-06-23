const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// This is the "kill switch" for the modern module exports resolution
// that conflicts with Node 20+ URL object strictness.
config.resolver.unstable_enablePackageExports = false;

// Optional: If you use an alias or complex pathing, ensure 
// sourceExts is explicitly defined to avoid resolution errors
config.resolver.sourceExts = ['js', 'jsx', 'ts', 'tsx', 'json'];

module.exports = config;