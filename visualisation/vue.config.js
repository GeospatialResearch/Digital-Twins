const cesiumSource = 'node_modules/cesium/Source';
const CopyWebpackPlugin = require('copy-webpack-plugin');
const path = require('path');
const webpack = require('webpack');

module.exports = {
  configureWebpack: {
    plugins: [
      new CopyWebpackPlugin([
        {from: path.join(cesiumSource, '../Build/Cesium/Workers'), to: 'Workers'},
        {from: path.join(cesiumSource, 'Assets'), to: 'Assets'},
        {from: path.join(cesiumSource, 'Widgets'), to: 'Widgets'}
      ]),
      new webpack.DefinePlugin({
        // Define relative base path in cesium for loading assets
        CESIUM_BASE_URL: JSON.stringify('')
      })
    ]
  }
}
