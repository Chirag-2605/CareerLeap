const { withAndroidManifest } = require("@expo/config-plugins");

const FEATURE_NAME = "android.hardware.screen.portrait";

function withOptionalPortraitFeature(config) {
  return withAndroidManifest(config, (config) => {
    const manifest = config.modResults.manifest;
    const features = manifest["uses-feature"] || [];

    const portraitFeature = features.find(
      (feature) => feature.$ && feature.$["android:name"] === FEATURE_NAME
    );

    if (portraitFeature) {
      portraitFeature.$["android:required"] = "false";
    } else {
      features.push({
        $: {
          "android:name": FEATURE_NAME,
          "android:required": "false"
        }
      });
    }

    manifest["uses-feature"] = features;
    return config;
  });
}

module.exports = withOptionalPortraitFeature;
