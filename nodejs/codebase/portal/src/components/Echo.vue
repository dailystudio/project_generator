<template>
  <v-app class="oms-app">
    <v-main>
      <v-container>
        <p id="topText">{{ $t("message.pageEchoTopText") }}</p>
        <v-text-field
            id="user-input"
            v-model="userInput"
            single-line
            :label="userInputLabel"
            :hint="userInputHint"
            color="#FD5700"
        ></v-text-field>
        <v-btn id="btn-echo" v-on:click="echo"
               outlined
               :color="buttonColor"
        >{{ $t("message.pageEchoBtnEcho") }}</v-btn>

        <p v-show="this.errorMessage" class="error-message">{{ this.errorMessage }}</p>
        <p v-show="this.echoMessage" class="echo-message">{{ this.echoMessage }}</p>
      </v-container>
    </v-main>
    <v-footer v-show="showFooter" fixed padless>
      <v-container>
        <v-col id="copyright"
               class="text-center"
               cols="12"
        >
          {{ $t("message.commonFooterCopyright") }} {{ new Date().getFullYear() }} &#169;
        </v-col>
      </v-container>
    </v-footer>

  </v-app>
</template>

<script>
  const axios = require('axios');

  export default {
    name: 'Echo',

    data() {
      return {
        fullPath: this.$route.fullPath,
        query: this.$route.query,
        theme: 'dark',
        locale: 'en',
        userInput: '',
        docHeight: document.documentElement.clientHeight,
        displayHeight: document.documentElement.clientHeight,
        showFooter: true,
        echoMessage: null,
        errorMessage: null,
      }
    },

    watch: {
      theme(theme) {
        console.log(`theme changed: ${theme}`);
        document.documentElement.setAttribute(
            'theme', theme);
      },
      locale(loc) {
        console.log(`locale changed: ${loc}`);
        this.$i18n.locale = loc
      },
      displayHeight: function () {
        if (this.docHeight > this.displayHeight) {
          this.showFooter = false;
        } else {
          this.showFooter = true;
        }
      }
    },

    computed: {
      userInputHint() {
        return this.$i18n.t('message.pageEchoInputHint');
      },

      userInputLabel() {
        return this.$i18n.t('message.pageEchoInputLabel');
      },

      buttonColor() {
        if (this.theme === 'dark') {
          return "#eee"
        } else {
          return "#1D1D1B"
        }
      },
    },


    mounted: function () {
      console.log(`query: ${JSON.stringify(this.query)}`);
      if (this.query.theme) {
        this.theme = this.query.theme
      }

      if (this.query.locale) {
        this.locale=this.query.locale
      }

      window.onresize = () => {
        return (()=> {
          this.displayHeight = document.documentElement.clientHeight;
        })();
      }

      this.$el.querySelectorAll('input').forEach(function (element) {
        element.setAttribute('autocomplete', 'off');
      });
    },

    methods: {

      echo: async function () {
        console.log(`message for echo: [${this.userInput}]`);

        try {
          let ret = await axios.get(`/v1/codebase/echo?message=${this.userInput}`, {
          });

          if (ret && ret.data && ret.data.code === 200) {
            console.log(`ret: [${JSON.stringify(ret.data)}]`);
            this.echoMessage = `[${ret.data.message}]`;
          } else {
            this.errorMessage = this.$t('message.errorFailedToCallApi');
          }
        } catch (e) {
          console.error(`failed to call apply api: ${e}`);
          this.errorMessage = this.$t('message.errorFailedToCallApi');
        }
      },

    }
  }
</script>

<style scoped>

.echo-message {
  color: var(--primary-color);
  padding: 20px 0;
}

#topText {
  font-size: 120px;
  padding: 0 10px;
  color: var(--on-background-color);
}

.oms-app .v-text-field {
  padding: 10px 50px;
}

@media (max-width: 280px) {
  #topText {
    font-size: 100px;
    padding: 20px;
  }
}

</style>
