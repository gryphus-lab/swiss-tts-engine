import React, { useState } from 'react';
import { StyleSheet, Text, View, TextInput, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { Audio } from 'expo-av';

// ⚠️ CHANGE THIS to your Mac's local Wi-Fi IP address
const MAC_IP = "192.168.1.102"; //NOSONAR
const API_URL = `http://${MAC_IP}:8000/api/v1`;

export default function App() {
  const [text, setText] = useState('Guten Tag, mein Name ist Abhay Singh.');
  const [dialect, setDialect] = useState('zurich');
  const [loading, setLoading] = useState(false);
  const [sound, setSound] = useState(null);

  async function generateAndPlayAudio() {
    setLoading(true);
    try {
      // 1. Request audio generation from the FastAPI container
      const response = await fetch(`${API_URL}/synthesize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, dialect })
      });
      
      if (!response.ok) throw new Error("Server error");
      const data = await response.json();
      
      // 2. Play the synthesized .wav back directly over Wi-Fi
      const audioUrl = `http://${MAC_IP}:8000${data.audio_url}?t=${new Date().getTime()}`;
      
      // Unload previous sound if it exists
      if (sound) {
        await sound.unloadAsync();
      }

      const { sound: newSound } = await Audio.Sound.createAsync(
        { uri: audioUrl },
        { shouldPlay: true }
      );
      setSound(newSound);

    } catch (error) {
      alert("Playback failed. Ensure Docker is running and your Mac IP is correct.");
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