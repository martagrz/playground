import numpy as np
import tensorflow as tf
import tensorflow_probability as tfp

def mlp(input, output_size):

    batch_size, _, filter_size = input.shape.as_list()
    output = tf.reshape(input, (-1, filter_size))
    output.set_shape((None, filter_size))

    output = tf.keras.layers.Dense(output_size, activation='relu')(output)
    output = tf.keras.layers.Dense(output_size)(output)
    output = tf.reshape(output, (batch_size,-1,output_size))
     
    return output

class DeterministicEncoder(tf.keras.Model):
    def __init__(self,output_size,attention=None):
        super(DeterministicEncoder,self).__init__()
        self._attention = attention
        self._output_size = output_size
         
    def call(self,x_context, y_context): 
        encoder_input = tf.concat([
            x_context, y_context], axis=-1)	
        hidden = mlp(encoder_input,self._output_size)
        
        if self._attention is not None:
            hidden = self._attention(x_context, y_context, hidden)

        return hidden
        
class LatentEncoder(tf.keras.Model):
    def __init__(self,output_size,num_latents):
        super(LatentEncoder,self).__init__()
        self._num_latents = num_latents
        self._output_size = output_size

    def call(self,x_context,y_context):
        encoder_input = tf.concat([
            x_context, y_context], axis=-1)

        hidden = mlp(encoder_input,self._output_size)
        hidden = tf.math.reduce_mean(hidden,axis=1)
        hidden =  tf.keras.layers.Dense((self._output_size + self._num_latents)/2, activation='relu')(hidden) #Relu
        mu = tf.keras.layers.Dense(self._num_latents)(hidden)
        log_sigma = tf.keras.layers.Dense(self._num_latents)(hidden)
        sigma = 0.1 + 0.9*tf.math.sigmoid(log_sigma)

        return tfp.distributions.Normal(loc=mu,scale=sigma)
        
    
class Decoder(tf.keras.Model):
    def __init__(self, output_size):
        super(Decoder,self).__init__()
        self._output_size = output_size
    
    def call(self,representation,x_target):
        hidden_input = tf.concat([representation, x_target], axis=-1)
        hidden = mlp(hidden_input,self._output_size)
        mu, log_sigma = tf.split(hidden, 2,axis=-1)
        sigma = 0.1 + 0.9 * tf.math.softplus(log_sigma)
        dist = tfp.distributions.MultivariateNormalDiag(loc=mu, scale_diag=sigma)
        
        return dist, mu, sigma  
       
class NPModel(tf.keras.Model):
    def __init__(self,
                latent_encoder_output_sizes, 
	        num_latents,               
		decoder_output_sizes, 
		deterministic_encoder_output_sizes,
		use_deterministic_encoder = True,
		attention=None):       

        super(NPModel,self).__init__()
        self._latent_encoder = LatentEncoder(latent_encoder_output_sizes, num_latents)
        self._use_deterministic_encoder = use_deterministic_encoder
        if self._use_deterministic_encoder:
              self._deterministic_encoder = DeterministicEncoder(deterministic_encoder_output_sizes,attention)
        self._decoder = Decoder(decoder_output_sizes)

    def call(self,query,num_targets,y_target=None):     

        (x_context, y_context), x_target = query

        prior = self._latent_encoder(x_context,y_context)

        if y_target is None:

             latent_rep = prior.sample()

        else:
            posterior = self._latent_encoder(x_target,y_target)
            latent_rep = posterior.sample()
                      
        latent_rep = tf.tile(tf.expand_dims(latent_rep,axis=1),
                             [1,num_targets,1])

        if self._use_deterministic_encoder:
            deterministic_rep = self._deterministic_encoder(
                x_context, y_context)
            representation = tf.concat([deterministic_rep,latent_rep], axis=-1)
        else:
            representation = latent_rep

        dist, mu, sigma = self._decoder(representation, x_target)

        if target_y is not None:
            log_p = dist.log_prob(y_target)
            posterior = self._latent_encoder(x_target, y_target)
            kl = tf.reduce_sum(
                tf.contrib.distributions.kl_divergence(posterior, prior), 
                axis=-1, keepdims=True)
            kl = tf.tile(kl, [1, num_targets])
            loss = - tf.reduce_mean(log_p - kl / tf.cast(num_targets, tf.float32))
        else:
            log_p = None
            kl = None
            loss = None

        return mu, sigma, log_p, kl, loss
    
        

print('Done')