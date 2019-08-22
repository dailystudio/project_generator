package com.dailystudio.codebase

import com.dailystudio.app.DevBricksApplication
import com.facebook.stetho.Stetho
import com.nostra13.universalimageloader.core.ImageLoader
import com.nostra13.universalimageloader.core.ImageLoaderConfiguration

class CodeBaseApplication : DevBricksApplication() {

    override fun onCreate() {
        super.onCreate()

        if (BuildConfig.USE_STETHO) {
            Stetho.initializeWithDefaults(this)
        }

        val config = ImageLoaderConfiguration.Builder(this).build()

        ImageLoader.getInstance().init(config)
    }

}