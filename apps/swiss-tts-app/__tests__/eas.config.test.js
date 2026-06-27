/**
 * Tests for eas.json EAS Build configuration.
 *
 * eas.json defines build profiles used by Expo Application Services (EAS)
 * to configure how the app is built for different environments.
 */

const easConfig = require("../eas.json");

describe("eas.json configuration", () => {
  describe("top-level structure", () => {
    it("is a valid JSON object", () => {
      expect(easConfig).toBeDefined();
      expect(typeof easConfig).toBe("object");
      expect(easConfig).not.toBeNull();
    });

    it("contains a 'build' key at the top level", () => {
      expect(easConfig).toHaveProperty("build");
    });

    it("does not have unexpected top-level keys", () => {
      const allowedTopLevelKeys = ["build"];
      const actualKeys = Object.keys(easConfig);
      actualKeys.forEach((key) => {
        expect(allowedTopLevelKeys).toContain(key);
      });
    });

    it("has exactly the expected top-level keys", () => {
      expect(Object.keys(easConfig)).toEqual(["build"]);
    });
  });

  describe("build profiles", () => {
    it("build section is an object", () => {
      expect(typeof easConfig.build).toBe("object");
      expect(easConfig.build).not.toBeNull();
    });

    it("contains a 'preview' build profile", () => {
      expect(easConfig.build).toHaveProperty("preview");
    });

    it("has exactly one build profile defined", () => {
      expect(Object.keys(easConfig.build)).toHaveLength(1);
      expect(Object.keys(easConfig.build)).toEqual(["preview"]);
    });
  });

  describe("preview build profile", () => {
    let previewProfile;

    beforeEach(() => {
      previewProfile = easConfig.build.preview;
    });

    it("is an object", () => {
      expect(typeof previewProfile).toBe("object");
      expect(previewProfile).not.toBeNull();
    });

    it("contains an 'android' configuration", () => {
      expect(previewProfile).toHaveProperty("android");
    });

    it("has exactly one platform configuration", () => {
      expect(Object.keys(previewProfile)).toHaveLength(1);
      expect(Object.keys(previewProfile)).toEqual(["android"]);
    });

    it("does not define an 'ios' configuration", () => {
      expect(previewProfile).not.toHaveProperty("ios");
    });
  });

  describe("preview android configuration", () => {
    let androidConfig;

    beforeEach(() => {
      androidConfig = easConfig.build.preview.android;
    });

    it("is an object", () => {
      expect(typeof androidConfig).toBe("object");
      expect(androidConfig).not.toBeNull();
    });

    it("specifies 'buildType' as 'apk'", () => {
      expect(androidConfig).toHaveProperty("buildType", "apk");
    });

    it("buildType is a string", () => {
      expect(typeof androidConfig.buildType).toBe("string");
    });

    it("buildType is not 'aab' (the production default)", () => {
      expect(androidConfig.buildType).not.toBe("aab");
    });

    it("has exactly one configuration key", () => {
      expect(Object.keys(androidConfig)).toHaveLength(1);
      expect(Object.keys(androidConfig)).toEqual(["buildType"]);
    });
  });

  describe("regression and boundary cases", () => {
    it("nested path build.preview.android.buildType resolves to 'apk'", () => {
      expect(easConfig?.build?.preview?.android?.buildType).toBe("apk");
    });

    it("build object is not an array", () => {
      expect(Array.isArray(easConfig.build)).toBe(false);
    });

    it("preview profile is not an array", () => {
      expect(Array.isArray(easConfig.build.preview)).toBe(false);
    });

    it("android config is not an array", () => {
      expect(Array.isArray(easConfig.build.preview.android)).toBe(false);
    });

    it("buildType value is non-empty string", () => {
      const { buildType } = easConfig.build.preview.android;
      expect(buildType.length).toBeGreaterThan(0);
    });

    it("config round-trips through JSON serialization without data loss", () => {
      const serialized = JSON.stringify(easConfig);
      const deserialized = JSON.parse(serialized);
      expect(deserialized).toEqual(easConfig);
    });
  });
});
