import {RouteConfig} from "vue-router";
import MapPage from "@/pages/MapPage.vue";
import AboutPage from "@/pages/AboutPage.vue"

/**
 * Sets router url endpoints to specific pages
 */
const routes: RouteConfig[] = [
  {
    path: "/",
    name: "Map",
    component: MapPage
  },
  {
    path: "/about",
    name: "About",
    component: AboutPage
  },
  {
    path: '*',
    redirect: '/'
  }
];
export default routes;
