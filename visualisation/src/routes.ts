import {RouteConfig} from "vue-router";
import AboutPage from "@/pages/AboutPage.vue"
import LicensePage from "@/pages/LicensePage.vue"
import MapPage from "@/pages/MapPage.vue";

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
    path: "/license",
    name: "License",
    component: LicensePage
  },
  {
    path: '*',
    redirect: '/'
  }
];
export default routes;
