// Configurate for Vite build tool

import {fileURLToPath, URL} from 'node:url'
import {defineConfig} from 'vite'
import {viteStaticCopy} from 'vite-plugin-static-copy'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // Copy necessary cesium assets into build
    viteStaticCopy({
      targets: [
        {src: './node_modules/cesium/Build/Cesium/Assets', dest: './'},
        {src: './node_modules/cesium/Build/Cesium/ThirdParty', dest: './'},
        {src: './node_modules/cesium/Build/Cesium/Widgets', dest: './'},
        {src: './node_modules/cesium/Build/Cesium/Workers', dest: './'},
      ]
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  }
})
