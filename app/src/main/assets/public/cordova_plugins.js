
  cordova.define('cordova/plugin_list', function(require, exports, module) {
    module.exports = [
      {
          "id": "com.adjust.sdk.Adjust",
          "file": "plugins/com.adjust.sdk/www/adjust.js",
          "pluginId": "com.adjust.sdk",
        "clobbers": [
          "Adjust"
        ]
        },
      {
          "id": "com.adjust.sdk.AdjustAdRevenue",
          "file": "plugins/com.adjust.sdk/www/adjust_ad_revenue.js",
          "pluginId": "com.adjust.sdk",
        "clobbers": [
          "AdjustAdRevenue"
        ]
        },
      {
          "id": "com.adjust.sdk.AdjustAppStorePurchase",
          "file": "plugins/com.adjust.sdk/www/adjust_app_store_purchase.js",
          "pluginId": "com.adjust.sdk",
        "clobbers": [
          "AdjustAppStorePurchase"
        ]
        },
      {
          "id": "com.adjust.sdk.AdjustAppStoreSubscription",
          "file": "plugins/com.adjust.sdk/www/adjust_app_store_subscription.js",
          "pluginId": "com.adjust.sdk",
        "clobbers": [
          "AdjustAppStoreSubscription"
        ]
        },
      {
          "id": "com.adjust.sdk.AdjustConfig",
          "file": "plugins/com.adjust.sdk/www/adjust_config.js",
          "pluginId": "com.adjust.sdk",
        "clobbers": [
          "AdjustConfig"
        ]
        },
      {
          "id": "com.adjust.sdk.AdjustDeeplink",
          "file": "plugins/com.adjust.sdk/www/adjust_deeplink.js",
          "pluginId": "com.adjust.sdk",
        "clobbers": [
          "AdjustDeeplink"
        ]
        },
      {
          "id": "com.adjust.sdk.AdjustEvent",
          "file": "plugins/com.adjust.sdk/www/adjust_event.js",
          "pluginId": "com.adjust.sdk",
        "clobbers": [
          "AdjustEvent"
        ]
        },
      {
          "id": "com.adjust.sdk.AdjustPlayStorePurchase",
          "file": "plugins/com.adjust.sdk/www/adjust_play_store_purchase.js",
          "pluginId": "com.adjust.sdk",
        "clobbers": [
          "AdjustPlayStorePurchase"
        ]
        },
      {
          "id": "com.adjust.sdk.AdjustPlayStoreSubscription",
          "file": "plugins/com.adjust.sdk/www/adjust_play_store_subscription.js",
          "pluginId": "com.adjust.sdk",
        "clobbers": [
          "AdjustPlayStoreSubscription"
        ]
        },
      {
          "id": "com.adjust.sdk.AdjustStoreInfo",
          "file": "plugins/com.adjust.sdk/www/adjust_store_info.js",
          "pluginId": "com.adjust.sdk",
        "clobbers": [
          "AdjustStoreInfo"
        ]
        },
      {
          "id": "com.adjust.sdk.AdjustThirdPartySharing",
          "file": "plugins/com.adjust.sdk/www/adjust_third_party_sharing.js",
          "pluginId": "com.adjust.sdk",
        "clobbers": [
          "AdjustThirdPartySharing"
        ]
        },
      {
          "id": "cordova-plugin-fullscreen.AndroidFullScreen",
          "file": "plugins/cordova-plugin-fullscreen/www/AndroidFullScreen.js",
          "pluginId": "cordova-plugin-fullscreen",
        "clobbers": [
          "AndroidFullScreen"
        ]
        },
      {
          "id": "cordova-plugin-purchase.CdvPurchase",
          "file": "plugins/cordova-plugin-purchase/www/store.js",
          "pluginId": "cordova-plugin-purchase",
        "clobbers": [
          "store",
          "CdvPurchase"
        ]
        },
      {
          "id": "cordova-plugin-chrome-apps-common.events",
          "file": "plugins/cordova-plugin-chrome-apps-common/events.js",
          "pluginId": "cordova-plugin-chrome-apps-common",
        "clobbers": [
          "chrome.Event"
        ]
        },
      {
          "id": "@herdwatch/cordova-plugin-chrome-apps-sockets-tcp.sockets.tcp",
          "file": "plugins/@herdwatch/cordova-plugin-chrome-apps-sockets-tcp/sockets.tcp.js",
          "pluginId": "@herdwatch/cordova-plugin-chrome-apps-sockets-tcp",
        "clobbers": [
          "chrome.sockets.tcp"
        ]
        },
      {
          "id": "cordova-plugin-chrome-apps-common.errors",
          "file": "plugins/cordova-plugin-chrome-apps-common/errors.js",
          "pluginId": "cordova-plugin-chrome-apps-common"
        },
      {
          "id": "cordova-plugin-chrome-apps-common.stubs",
          "file": "plugins/cordova-plugin-chrome-apps-common/stubs.js",
          "pluginId": "cordova-plugin-chrome-apps-common"
        },
      {
          "id": "cordova-plugin-chrome-apps-common.helpers",
          "file": "plugins/cordova-plugin-chrome-apps-common/helpers.js",
          "pluginId": "cordova-plugin-chrome-apps-common"
        }
    ];
    module.exports.metadata =
    // TOP OF METADATA
    {
      "@herdwatch/cordova-plugin-chrome-apps-sockets-tcp": "1.4.0",
      "com.adjust.sdk": "5.6.0",
      "cordova-plugin-chrome-apps-common": "1.0.7",
      "cordova-plugin-fullscreen": "1.3.0",
      "cordova-plugin-purchase": "13.13.1"
    };
    // BOTTOM OF METADATA
    });
    