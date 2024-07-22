/** Sets up and mounts Vue app to #app element */
import {createApp} from "vue";
import {createRouter, createWebHistory} from "vue-router";
// todo
// import BootstrapVue from "bootstrap-vue";
import App from '@/App.vue'
import routes from "@/routes";

//todo
// import 'bootstrap/dist/css/bootstrap.css'
// import 'bootstrap-vue/dist/bootstrap-vue.css'
import "@/assets/base-style.css"

const router = createRouter({
  routes,
  history: createWebHistory(import.meta.env.BASE_URL)
});

const app = createApp(App)

app.use(router)
// app.use(BootstrapVue) todo

app.mount('#app')
