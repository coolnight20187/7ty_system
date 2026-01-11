package com.ty7.smsreader;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        registerPlugin(SMSReaderPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
