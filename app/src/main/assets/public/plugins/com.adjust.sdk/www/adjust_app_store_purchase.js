cordova.define("com.adjust.sdk.AdjustAppStorePurchase", function(require, exports, module) { 
function AdjustAppStorePurchase(productId, transactionId) {
    this.productId = productId;
    this.transactionId = transactionId;
}

module.exports = AdjustAppStorePurchase;
});