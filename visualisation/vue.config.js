const cesiumSource = 'node_modules/cesium/Source';
const CopyWebpackPlugin = require('copy-webpack-plugin');
const path = require('path');

module.exports = {
  configureWebpack: {
    plugins: [
      new CopyWebpackPlugin([
        {from: path.join(cesiumSource, '../Build/Cesium/Workers'), to: 'Workers'},
        {from: path.join(cesiumSource, 'Assets'), to: 'Assets'},
        {from: path.join(cesiumSource, 'Widgets'), to: 'Widgets'}
      ])
    ]
  }
}
