// Handles the routing configuration, for which URLs point to which pages.

import type {RouteRecordRaw} from "vue-router";
import AboutPage from "@/pages/AboutPage.vue"
import LicensePage from "@/pages/LicensePage.vue"
import MapPage from "@/pages/MapPage.vue";

/**
 * Sets router url endpoints to specific pages
 */
const routes: RouteRecordRaw[] = [
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
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
];
export default routes;
