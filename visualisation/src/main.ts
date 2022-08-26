/** Sets up and mounts Vue app to #app element */
import Vue from 'vue';
import VueRouter from "vue-router";
import BootstrapVue from "bootstrap-vue";

import App from '@/App.vue'
import routes from "@/routes";

import 'bootstrap/dist/css/bootstrap.css'
import 'bootstrap-vue/dist/bootstrap-vue.css'

import "@/assets/base-style.css"

// Set plugins
Vue.use(VueRouter);
Vue.use(BootstrapVue);

Vue.config.productionTip = false;

const router = new VueRouter({
  routes,
  mode: 'history'
});

new Vue({
  router,
  render: h => h(App)
}).$mount('#app');
