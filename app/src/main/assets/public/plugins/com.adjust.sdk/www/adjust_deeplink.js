cordova.define("com.adjust.sdk.AdjustDeeplink", function(require, exports, module) { 
function AdjustDeeplink(deeplink) {
    this.deeplink = deeplink;
    this.referrer = null;
}

AdjustDeeplink.prototype.setReferrer = function(referrer) {
    this.referrer = referrer;
};

module.exports = AdjustDeeplink;
});