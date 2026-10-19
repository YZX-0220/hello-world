import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import { startSiteTraffic } from './composables/useSiteTraffic';

const app = createApp(App);
startSiteTraffic(router);
app.use(createPinia());
app.use(router);
app.mount('#app');
