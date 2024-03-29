# -*- coding: utf-8 -*-
"""
Created on Tue Feb 23 09:00:02 2021

@author: Ajay Solanki
"""
#Importing dependencies 
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
plt.style.use('seaborn')
import quandl
plt.rcParams["figure.figsize"] = (20,10) #change this if you want to reduce the plot images
import locale
import tensorflow as tf
from tensorflow.keras.models import *
from tensorflow.keras.layers import *
import yfinance as yf
from rutils.YahooData import Puller


locale.setlocale(locale.LC_NUMERIC, '') 

d_k = 256
d_v = 256
n_heads = 16
ff_dim = 512
seq_len = 128
#Changes to be made to support yahoo streamer
class DataOperation:
    def load_data(self):
        scriptcode = "BOM500325"
        api_key = "HHCBs8CFrnTXyu__s7xv"
        self.data = quandl.get("BSE/" + scriptcode,  start_date="2010-07-01", end_date=date.today(),api_key =api_key)
        self.data.reset_index(level=0, inplace=True)
        
    
    def plot_daily_close_price(self):
        fig = plt.figure(figsize=(15,10))
        st = fig.suptitle(" Close Price and Volume", fontsize=20)
        st.set_y(0.92)
        ax1 = fig.add_subplot(211)
        ax1.plot(self.data['Close'], label=' Close Price')
        ax1.set_xticks(range(0, self.data.shape[0], 1464))
        ax1.set_xticklabels(self.data['Date'].loc[::1464])
        ax1.set_ylabel('Close Price', fontsize=18)
        ax1.legend(loc="upper left", fontsize=12)
    
        ax2 = fig.add_subplot(212)
        ax2.plot(self.data['Total Trade Quantity'], label=' Volume')
        ax2.set_xticks(range(0, self.data.shape[0], 1464))
        ax2.set_xticklabels(self.data['Date'].loc[::1464])
        ax2.set_ylabel('Volume', fontsize=18)
        ax2.legend(loc="upper left", fontsize=12)
        
    
    def normalize_data(self):
        df = self.data
        #df.reset_index(level=0, inplace=True)
        df['Open'] = df['Open'].pct_change() 
        df['High'] = df['High'].pct_change() 
        df['Low'] = df['Low'].pct_change()
        df['Close'] = df['Close'].pct_change() 
        df['Total Trade Quantity'] = df['Total Trade Quantity'].pct_change()
        df.dropna(how='any', axis=0, inplace=True) 
        min_return = min(df[['Open', 'High', 'Low', 'Close']].min(axis=0))
        max_return = max(df[['Open', 'High', 'Low', 'Close']].max(axis=0))
        df['Open'] = (df['Open'] - min_return) / (max_return - min_return)
        df['High'] = (df['High'] - min_return) / (max_return - min_return)
        df['Low'] = (df['Low'] - min_return) / (max_return - min_return)
        df['Close'] = (df['Close'] - min_return) / (max_return - min_return)
        
        min_volume = df['Total Trade Quantity'].min(axis=0)
        max_volume = df['Total Trade Quantity'].max(axis=0)
        df['Total Trade Quantity'] = (df['Total Trade Quantity'] - min_volume) / (max_volume - min_volume)
        times = sorted(df.index.values)
        last_10pct = sorted(df.index.values)[-int(0.1*len(times))] # Last 10% of series
        last_20pct = sorted(df.index.values)[-int(0.2*len(times))] # Last 20% of series

        df_train = df[(df.index < last_20pct)]  # Training data are 80% of total data
        df_val = df[(df.index >= last_20pct) & (df.index < last_10pct)]
        df_test = df[(df.index >= last_10pct)]
        
        # Remove date column
        df_train.drop(columns=['Date'], inplace=True)
        df_val.drop(columns=['Date'], inplace=True)
        df_test.drop(columns=['Date'], inplace=True)
        self.train = df_train.values
        self.val = df_val.values
        self.test = df_test.values
        print('Training data shape: {}'.format(self.train.shape))
        print('Validation data shape: {}'.format(self.val.shape))
        print('Test data shape: {}'.format(self.test .shape))
    
    def dataops(self,elements,seq_len):
        print("Shape is {}".format(elements.shape))
        x , y = [],[]
        for i in range(seq_len, elements.shape[0]):
            x.append(elements[i-seq_len:i])
            y.append(elements[:, 5][i])
        x, y = np.array(x), np.array(y) 
        return(x,y)
        
    def build_data(self,seq_len):
        print('--Training data shape: {}'.format(self.train.shape))
        print('--Validation data shape: {}'.format(self.val.shape))
        print('--Test data shape: {}'.format(self.test.shape))
        self.x_train , self.y_train =self.dataops(self.train, seq_len)
        self.x_val , self.y_val =self.dataops(self.val, seq_len)
        self.x_test , self.y_test =self.dataops(self.test, seq_len)
        
        print('Training set shape', self.x_train.shape, self.y_train.shape)
        print('Validation set shape', self.x_val.shape, self.y_val.shape)
        print('Testing set shape' ,self.x_test.shape, self.y_test.shape)
        
class Time2Vector(Layer):
  def __init__(self, seq_len, **kwargs):
    super(Time2Vector, self).__init__()
    self.seq_len = seq_len

  def build(self, input_shape):
    '''Initialize weights and biases with shape (batch, seq_len)'''
    self.weights_linear = self.add_weight(name='weight_linear',
                                shape=(int(self.seq_len),),
                                initializer='uniform',
                                trainable=True)
    
    self.bias_linear = self.add_weight(name='bias_linear',
                                shape=(int(self.seq_len),),
                                initializer='uniform',
                                trainable=True)
    
    self.weights_periodic = self.add_weight(name='weight_periodic',
                                shape=(int(self.seq_len),),
                                initializer='uniform',
                                trainable=True)

    self.bias_periodic = self.add_weight(name='bias_periodic',
                                shape=(int(self.seq_len),),
                                initializer='uniform',
                                trainable=True)

  def call(self, x):
    '''Calculate linear and periodic time features'''
    x = tf.math.reduce_mean(x[:,:,:4], axis=-1) 
    time_linear = self.weights_linear * x + self.bias_linear # Linear time feature
    time_linear = tf.expand_dims(time_linear, axis=-1) # Add dimension (batch, seq_len, 1)
    
    time_periodic = tf.math.sin(tf.multiply(x, self.weights_periodic) + self.bias_periodic)
    time_periodic = tf.expand_dims(time_periodic, axis=-1) # Add dimension (batch, seq_len, 1)
    return tf.concat([time_linear, time_periodic], axis=-1) # shape = (batch, seq_len, 2)
   
  def get_config(self): # Needed for saving and loading model with custom layer
    config = super().get_config().copy()
    config.update({'seq_len': self.seq_len})
    return config
        
        


class SingleAttention(tf.keras.layers.Layer):
    def __init__(self, d_k, d_v):
        super(SingleAttention, self).__init__()
        self.d_k = d_k
        self.d_v = d_v
    
    def build(self,input_shape):
        self.query = Dense(self.d_k, 
                       input_shape=input_shape, 
                       kernel_initializer='glorot_uniform', 
                       bias_initializer='glorot_uniform')
        self.key = Dense(self.d_k,
                           input_shape=input_shape,
                           kernel_initializer='glorot_uniform',
                           bias_initializer='glorot_uniform')
        self.value = Dense(self.d_v,
                           input_shape=input_shape,
                           kernel_initializer='glorot_uniform',
                           bias_initializer='glorot_uniform')
    
    def call(self, inputs):
        q = self.query(inputs[0])
        k = self.query(inputs[1])
        
        attn_weights = tf.matmul(q,k,transpose_b= True)
        attn_weights = tf.map_fn(lambda x: x/np.sqrt(self.d_k), attn_weights)
        attn_weights = tf.nn.softmax(attn_weights,axis=1)
        
        v = self.query(inputs[2])
        attn_out = tf.matmul(attn_weights, v)
        return attn_out

class MultiAttention(tf.keras.layers.Layer):
    def __init__(self, d_k, d_v,n_heads):
        super(MultiAttention, self).__init__()
        self.d_k = d_k
        self.d_v = d_v
        self.n_heads = n_heads
        self.attn_heads =list()
        
    def build(self,input_shape):
        for n in range(self.n_heads):
            self.attn_heads.append(SingleAttention(self.d_k, self.d_v))
        self.linear = Dense(input_shape[0][-1],
                      kernel_initializer='glorot_uniform', 
                      bias_initializer='glorot_uniform')
            
    
    def call(self, inputs):
        attn = [self.attn_heads[i](inputs) for i in range(self.n_heads)]
        concat_attn = tf.concat(attn, axis =-1)
        multi_linear = self.linear(concat_attn)
        return multi_linear

class TransformerEncoder(Layer):
  def __init__(self, d_k, d_v, n_heads, ff_dim, dropout=0.1, **kwargs):
    super(TransformerEncoder, self).__init__()
    self.d_k = d_k
    self.d_v = d_v
    self.n_heads = n_heads
    self.ff_dim = ff_dim
    self.attn_heads = list()
    self.dropout_rate = dropout

  def build(self, input_shape):
    self.attn_multi = MultiAttention(self.d_k, self.d_v, self.n_heads)
    self.attn_dropout = Dropout(self.dropout_rate)
    self.attn_normalize = LayerNormalization(input_shape=input_shape, epsilon=1e-6)

    self.ff_conv1D_1 = Conv1D(filters=self.ff_dim, kernel_size=1, activation='relu')
    # input_shape[0]=(batch, seq_len, 7), input_shape[0][-1] = 7 
    self.ff_conv1D_2 = Conv1D(filters=input_shape[0][-1], kernel_size=1) 
    self.ff_dropout = Dropout(self.dropout_rate)
    self.ff_normalize = LayerNormalization(input_shape=input_shape, epsilon=1e-6)    
  
  def call(self, inputs): # inputs = (in_seq, in_seq, in_seq)
    attn_layer = self.attn_multi(inputs)
    attn_layer = self.attn_dropout(attn_layer)
    attn_layer = self.attn_normalize(inputs[0] + attn_layer)

    ff_layer = self.ff_conv1D_1(attn_layer)
    ff_layer = self.ff_conv1D_2(ff_layer)
    ff_layer = self.ff_dropout(ff_layer)
    ff_layer = self.ff_normalize(inputs[0] + ff_layer)
    return ff_layer 

  def get_config(self): # Needed for saving and loading model with custom layer
    config = super().get_config().copy()
    config.update({'d_k': self.d_k,
                   'd_v': self.d_v,
                   'n_heads': self.n_heads,
                   'ff_dim': self.ff_dim,
                   'attn_heads': self.attn_heads,
                   'dropout_rate': self.dropout_rate})
    return config          
class Transformer:  
    def create_model(self):

             
        '''Initialize time and transformer layers'''
        time_embedding = Time2Vector(seq_len)
        attn_layer1 = TransformerEncoder(d_k, d_v, n_heads, ff_dim)
        attn_layer2 = TransformerEncoder(d_k, d_v, n_heads, ff_dim)
        attn_layer3 = TransformerEncoder(d_k, d_v, n_heads, ff_dim)
    
        '''Construct model'''
        in_seq = Input(shape=(seq_len, 7))
        x = time_embedding(in_seq)
        x = Concatenate(axis=-1)([in_seq, x])
        x = attn_layer1((x, x, x))
        x = attn_layer2((x, x, x))  
        x = attn_layer3((x, x, x))
        x = GlobalAveragePooling1D(data_format='channels_first')(x)
        x = Dropout(0.1)(x)
        x = Dense(64, activation='relu')(x)
        x = Dropout(0.1)(x)
        out = Dense(1, activation='linear')(x)
    
        model = Model(inputs=in_seq, outputs=out)
        model.compile(loss='mse', optimizer='adam', metrics=['mae', 'mape'])
        self.model = model
        return (model)
             
    def execute(self,X_train,y_train, X_val, y_val, X_test, y_test,dataops):
        callback = tf.keras.callbacks.ModelCheckpoint('Transformer+TimeEmbedding.hdf5', 
                                              monitor='val_loss', 
                                              save_best_only=True, verbose=1)
        history = self.model.fit(X_train, y_train, 
                    batch_size=batch_size, 
                    epochs=7, 
                    callbacks=[callback],
                    validation_data=(X_val, y_val))  
        model = tf.keras.models.load_model('Transformer+TimeEmbedding.hdf5',
                                   custom_objects={'Time2Vector': Time2Vector, 
                                                   'SingleAttention': SingleAttention,
                                                   'MultiAttention': MultiAttention,
                                                   'TransformerEncoder': TransformerEncoder})
        train_pred = model.predict(X_train)
        val_pred = model.predict(X_val)
        test_pred = model.predict(X_test)
        
        #Print evaluation metrics for all datasets
        train_eval = model.evaluate(X_train, y_train, verbose=0)
        val_eval = model.evaluate(X_val, y_val, verbose=0)
        test_eval = model.evaluate(X_test, y_test, verbose=0)
        print(' ')
        print('Evaluation metrics')
        print('Training Data - Loss: {:.4f}, MAE: {:.4f}, MAPE: {:.4f}'.format(train_eval[0], train_eval[1], train_eval[2]))
        print('Validation Data - Loss: {:.4f}, MAE: {:.4f}, MAPE: {:.4f}'.format(val_eval[0], val_eval[1], val_eval[2]))
        print('Test Data - Loss: {:.4f}, MAE: {:.4f}, MAPE: {:.4f}'.format(test_eval[0], test_eval[1], test_eval[2]))
        
        ###############################################################################
        '''Display results'''
        
        fig = plt.figure(figsize=(15,20))
        st = fig.suptitle("Transformer + TimeEmbedding Model", fontsize=22)
        st.set_y(0.92)
        
        #Plot training data results
        ax11 = fig.add_subplot(311)
        ax11.plot(dataops.train[:, 3], label=' Closing Returns')
        ax11.plot(np.arange(seq_len, train_pred.shape[0]+seq_len), train_pred, linewidth=3, label='Predicted Closing Returns')
        ax11.set_title("Training Data", fontsize=18)
        ax11.set_xlabel('Date')
        ax11.set_ylabel(' Closing Returns')
        ax11.legend(loc="best", fontsize=12)
        
        #Plot validation data results
        ax21 = fig.add_subplot(312)
        ax21.plot(dataops.val[:, 3], label=' Closing Returns')
        ax21.plot(np.arange(seq_len, val_pred.shape[0]+seq_len), val_pred, linewidth=3, label='Predicted  Closing Returns')
        ax21.set_title("Validation Data", fontsize=18)
        ax21.set_xlabel('Date')
        ax21.set_ylabel(' Closing Returns')
        ax21.legend(loc="best", fontsize=12)
        
        #Plot test data results
        ax31 = fig.add_subplot(313)
        ax31.plot(dataops.test[:, 3], label=' Closing Returns')
        ax31.plot(np.arange(seq_len, test_pred.shape[0]+seq_len), test_pred, linewidth=3, label='Predicted  Closing Returns')
        ax31.set_title("Test Data", fontsize=18)
        ax31.set_xlabel('Date')
        ax31.set_ylabel(' Closing Returns')
        ax31.legend(loc="best", fontsize=12)
     
         
        
        
        
    
        
        
#Transformer -------        
     
batch_size = 32
seq_len = 128

d_k = 256
d_v = 256
n_heads = 16
ff_dim = 512    
   
dataops = DataOperation()
dataops.load_data()
dataops.plot_daily_close_price()
dataops.normalize_data()
dataops.build_data(128)

transformer = Transformer()
print("Execution...")
transformer.create_model()
transformer.execute(dataops.x_train, dataops.y_train, dataops.x_val, dataops.y_val, dataops.x_test, dataops.y_test,dataops)

