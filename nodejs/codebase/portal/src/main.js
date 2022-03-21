import Vue from 'vue'
import VueI18n from 'vue-i18n'
import VueRouter from 'vue-router'
import vuetify from './plugins/vuetify';
import App from './App'
import Echo from './components/Echo'

import './assets/common.scss';

Vue.config.productionTip = false
Vue.use(VueRouter)
Vue.use(VueI18n)

const messages = {
  en: {
    message: {
      pageEchoTopText: "Hello",
      pageEchoBtnEcho: "Echo",
      pageEchoInputLabel: "Message",
      pageEchoInputHint: "Enter something you want to be echoed",

      commonFooterCopyright: "Daily Studio. Copyright",
      errorFailedToCallApi: "Failed to call API"
    }
  },
  cn: {
    message: {
      pageEchoTopText: "你好",
      pageEchoBtnEcho: "回显",
      pageEchoInputLabel: "消息",
      pageEchoInputHint: "输入任意想被回显的内容",

      commonFooterCopyright: "Daily Studio. 版权所有"
    }
  }
}

const i18n = new VueI18n({
  locale: 'en', // set locale
  messages: messages,
});

const routes = [
  {
    path: '/',
    redirect: '/echo'
  },
  {
    path: '/echo',
    component: Echo
  },
]

const router = new VueRouter({
  mode: 'history',
  routes
})

new Vue({
  i18n,
  router,
  vuetify,
  render: h => h(App),
}).$mount('#app')
