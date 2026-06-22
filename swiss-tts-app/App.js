import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, TextInput, TouchableOpacity, ActivityIndicator, Alert } from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { Audio } from 'expo-av';

if (!process.env.EXPO_PUBLIC_API_IP) {
  throw new Error('EXPO_PUBLIC_API_IP environment variable is not defined. Please configure it in your .env file.');
}

const API_URL = `http://${process.env.EXPO_PUBLIC_API_IP}:8000/api/v1`;

/**
 * Swiss dialect text-to-speech interface for mobile.
 * 
 * Allows users to input text, select a Swiss dialect (Zürich, Bern, or Basel), and synthesize speech via network API.
 */
export default function App() {
  const [text, setText] = useState('Guten Tag, mein Name ist Abhay Singh.');
  const [dialect, setDialect] = useState('zurich');
  const [loading, setLoading] = useState(false);
  const [sound, setSound] = useState(null);

  useEffect(() => {
    return () => {
      if (sound) {
        sound.unloadAsync();
      }
    };
  }, []);

  /**
   * Synthesizes text-to-speech for the selected dialect and plays the resulting audio.
   */
  async function generateAndPlayAudio() {
    // Validate text input
    if (!text || text.trim() === '') {
      Alert.alert('Input Required', 'Please enter some text to synthesize.');
      return;
    }

    setLoading(true);
    try {
      // 1. Request audio generation from the FastAPI container
      const response = await fetch(`${API_URL}/synthesize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, dialect })
      });

      if (!response.ok) {
        if (response.status >= 500) {
          throw new Error(`SERVER_ERROR:${response.status}`);
        } else if (response.status >= 400) {
          throw new Error(`CLIENT_ERROR:${response.status}`);
        }
        throw new Error(`HTTP_ERROR:${response.status}`);
      }

      let data;
      try {
        data = await response.json();
      } catch (parseError) {
        throw new Error('JSON_PARSE_ERROR');
      }

      // 2. Play the synthesized .wav back directly over Wi-Fi
      if (!process.env.EXPO_PUBLIC_API_IP) {
        throw new Error('EXPO_PUBLIC_API_IP environment variable is not defined. Please configure it in your .env file.');
      }
      const audioUrl = `http://${process.env.EXPO_PUBLIC_API_IP}:8000${data.audio_url}?t=${new Date().getTime()}`;

      // Unload previous sound if it exists
      if (sound) {
        await sound.unloadAsync();
      }

      let newSound;
      try {
        const result = await Audio.Sound.createAsync(
          { uri: audioUrl },
          { shouldPlay: true }
        );
        newSound = result.sound;
        setSound(newSound);
      } catch (audioError) {
        if (newSound) {
          await newSound.unloadAsync();
        }
        throw new Error('AUDIO_PLAYBACK_ERROR');
      }

    } catch (error) {
      let errorMessage = 'An unexpected error occurred.';

      if (error.message === 'AUDIO_PLAYBACK_ERROR') {
        errorMessage = 'Failed to load or play the audio file. Please check your connection and try again.';
      } else if (error.message === 'JSON_PARSE_ERROR') {
        errorMessage = 'Server returned an invalid response. Please try again.';
      } else if (error.message.startsWith('SERVER_ERROR:')) {
        const status = error.message.split(':')[1];
        errorMessage = `Server error (${status}). The service may be temporarily unavailable.`;
      } else if (error.message.startsWith('CLIENT_ERROR:')) {
        const status = error.message.split(':')[1];
        errorMessage = `Request error (${status}). Please check your input and try again.`;
      } else if (error.message.startsWith('HTTP_ERROR:')) {
        const status = error.message.split(':')[1];
        errorMessage = `HTTP error (${status}). Please try again.`;
      } else if (error.message === 'Network request failed' || error.name === 'TypeError') {
        errorMessage = 'Network connection failed. Ensure Docker is running and your API IP is configured correctly.';
      }

      Alert.alert('Error', errorMessage);
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>🇨🇭 Swiss TTS Mobile</Text>
      
      <Text style={styles.label}>Input Text (Any Language)</Text>
      <TextInput 
        style={styles.input} 
        multiline 
        value={text} 
        onChangeText={setText} 
      />
      
      <Text style={styles.label}>Target Dialect</Text>
      <View style={styles.pickerContainer}>
        <Picker 
          selectedValue={dialect} 
          onValueChange={(itemValue) => setDialect(itemValue)}
          style={styles.picker}
        >
          <Picker.Item label="Zürich (Züritüütsch)" value="zurich" />
          <Picker.Item label="Bern (Bärndütsch)" value="bern" />
          <Picker.Item label="Basel (Baaseldytsch)" value="basel" />
        </Picker>
      </View>

      {loading ? (
        <ActivityIndicator size="large" color="#e11d48" style={{ marginTop: 20 }} />
      ) : (
        <TouchableOpacity style={styles.button} onPress={generateAndPlayAudio}>
          <Text style={styles.buttonText}>Speak Dialect</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, justifyContent: 'center', backgroundColor: '#f4f4f5' },
  title: { fontSize: 26, fontWeight: 'bold', color: '#e11d48', marginBottom: 32, textAlign: 'center' },
  label: { fontSize: 14, fontWeight: '600', color: '#4b5563', marginBottom: 6 },
  input: { backgroundColor: 'white', padding: 16, borderRadius: 8, height: 120, marginBottom: 20, borderWidth: 1, borderColor: '#e4e4e7', textAlignVertical: 'top' },
  pickerContainer: { backgroundColor: 'white', borderRadius: 8, borderWidth: 1, borderColor: '#e4e4e7', marginBottom: 32, overflow: 'hidden' },
  picker: { height: 50, width: '100%' },
  button: { background: '#e11d48', backgroundColor: '#e11d48', padding: 16, borderRadius: 8, alignItems: 'center' },
  buttonText: { color: 'white', fontSize: 16, fontWeight: 'bold' }
});