package com.dailystudio.codebase

import androidx.appcompat.app.AppCompatActivity
import android.os.Bundle
import androidx.appcompat.widget.Toolbar

class MainActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
    }


    override fun onResume() {
        super.onResume()

        val topBar: Toolbar? = findViewById(R.id.topAppBar)

        topBar?.let {
            setSupportActionBar(it)
        }

    }

}
