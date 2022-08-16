/** Sets up and mounts Vue app to #app element */
import Vue from 'vue'

import App from '@/App.vue'

Vue.config.productionTip = false

new Vue({
  render: h => h(App)
}).$mount('#app')
