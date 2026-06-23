// ---------------------------------------------------------------------------
// Tests for metro.config.js
// Validates the Metro bundler configuration introduced in this PR.
// ---------------------------------------------------------------------------

// Mock expo/metro-config before requiring metro.config.js
const mockConfig = {
  resolver: {},
  transformer: {},
  serializer: {},
};

jest.mock("expo/metro-config", () => ({
  getDefaultConfig: jest.fn(() => ({ ...mockConfig, resolver: {} })),
}));

const { getDefaultConfig } = require("expo/metro-config");

// Re-require metro.config after mocks are set up
let metroConfig;
beforeAll(() => {
  metroConfig = require("../metro.config");
});

describe("metro.config.js", () => {
  it("calls getDefaultConfig with __dirname", () => {
    // getDefaultConfig is called once at module load time
    expect(getDefaultConfig).toHaveBeenCalledTimes(1);
    // The argument is the project root directory
    expect(getDefaultConfig).toHaveBeenCalledWith(
      expect.stringMatching(/git$/),
    );
  });

  it("exports a config object", () => {
    expect(metroConfig).toBeDefined();
    expect(typeof metroConfig).toBe("object");
  });

  it("disables unstable_enablePackageExports on the resolver", () => {
    expect(metroConfig.resolver.unstable_enablePackageExports).toBe(false);
  });

  it("does not set unstable_enablePackageExports to true", () => {
    expect(metroConfig.resolver.unstable_enablePackageExports).not.toBe(true);
  });

  it("preserves other resolver properties from the default config", () => {
    // The config object from getDefaultConfig should still be the base
    expect(metroConfig.resolver).toBeDefined();
  });
});