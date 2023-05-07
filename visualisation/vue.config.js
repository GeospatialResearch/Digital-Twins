// Webpack configuration file for bundling code
const CopyWebpackPlugin = require('copy-webpack-plugin');
const path = require('path');

const cesiumSource = 'node_modules/cesium/Source';

/**
 * @type {import('@vue/cli-service').ProjectOptions}
 */
module.exports = {
  configureWebpack: {
    plugins: [
      new CopyWebpackPlugin([
        {from: path.join(cesiumSource, '../Build/Cesium/Workers'), to: 'Workers'},
        {from: path.join(cesiumSource, 'Assets'), to: 'Assets'},
        {from: path.join(cesiumSource, 'Widgets'), to: 'Widgets'}
      ])
    ]
  },
  chainWebpack(config) {
   // Add rule so that the LICENSE text can be read into a WebPage
   config.module
      .rule('raw')
      .test(/LICENSE$/)
      .use('raw-loader')
      .loader('raw-loader')
      .end()
  }
}
