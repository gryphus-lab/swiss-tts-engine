import React, { useState, useEffect } from "react";
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  SafeAreaView,
} from "react-native";
import { Picker } from "@react-native-picker/picker";
import { Audio } from "expo-av";
import { StatusBar } from "expo-status-bar";
import { initLlama } from 'llama.rn';
import * as FileSystem from 'expo-file-system'; // Make sure expo-file-system is installed

export default function App() {
  const [text, setText] = useState("Guten Tag, mein Name ist Abhay Singh.");
  const [dialect, setDialect] = useState("zurich");
  const [loading, setLoading] = useState(false);
  const [sound, setSound] = useState(null);

  const API_IP = process.env.EXPO_PUBLIC_API_IP;

  useEffect(() => {
        async function loadLocalModel() {
      try {
        setStatusMessage('Mounting safe sandbox allocation...');
        
        // Dynamically resolves to the secure, internal app directory on Android 17
        const modelPath = `${FileSystem.documentDirectory}gemma-4-E4B-it-Q4_K_M.gguf`;

        const context = await initLlama({
          model: modelPath,
          use_mlock: true,      // Tells the kernel to pin the memory space
          n_ctx: 1024,          
          n_gpu_layers: 99,     // Offload layers to your Pixel 10 Tensor NPU
        });

        setLlamaContext(context);
        setIsModelLoading(false);
        setStatusMessage('Tensor engine ready. Model loaded fully on-device.');
      } catch (error) {
        console.error("Local inference initiation failed:", error);
        setStatusMessage(`Engine crash: ${error.message}`);
      }
    }
    if (!API_IP) {
      throw new Error(
        "EXPO_PUBLIC_API_IP environment variable is not defined. Please configure it in your .env file.",
      );
    }
    return () => {
      if (sound) {
        sound.unloadAsync();
      }
    };
  }, [sound, API_IP]);

  async function generateAndPlayAudio() {
    if (!text.trim()) {
      Alert.alert("Input Required", "Please enter some text to synthesize.");
      return;
    }

    setLoading(true);
    try {
      if (sound) {
        await sound.unloadAsync();
        setSound(null);
      }

      const response = await fetch(`http://${API_IP}:8000/api/v1/synthesize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, dialect }),
      });

      if (!response.ok) {
        if (response.status >= 500) {
          Alert.alert(
            "Error",
            `Server error (${response.status}). The service may be temporarily unavailable.`,
          );
        } else if (response.status >= 400) {
          Alert.alert(
            "Error",
            `Request error (${response.status}). Please check your input and try again.`,
          );
        } else {
          Alert.alert("Error", `HTTP error (${response.status}). Please try again.`);
        }
        setLoading(false);
        return;
      }

      const data = await response.json();
      const audioUrl = `http://${API_IP}:8000${data.audio_url}?t=${Date.now()}`;

      const { sound: newSound } = await Audio.Sound.createAsync(
        { uri: audioUrl },
        { shouldPlay: true },
      );
      setSound(newSound);
    } catch (error) {
      if (error instanceof SyntaxError) {
        Alert.alert(
          "Error",
          "Server returned an invalid response. Please try again.",
        );
      } else if (
        error.message === "Network request failed" ||
        error instanceof TypeError
      ) {
        Alert.alert(
          "Error",
          "Network connection failed. Ensure Docker is running and your API IP is configured correctly.",
        );
      } else if (
        error.message.includes("Could not load audio") ||
        error.message.includes("Failed to load")
      ) {
        Alert.alert(
          "Error",
          "Failed to load or play the audio file. Please check your connection and try again.",
        );
      } else {
        Alert.alert("Error", "An unexpected error occurred.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="auto" />
      <View style={styles.content}>
        <Text style={styles.title}>🇨🇭 Swiss TTS Mobile</Text>

        <View style={styles.section}>
          <Text style={styles.label}>Input Text (Any Language)</Text>
          <TextInput
            style={styles.input}
            multiline
            numberOfLines={4}
            value={text}
            onChangeText={setText}
            placeholder="Enter text here..."
          />
        </View>

        <View style={styles.section}>
          <Text style={styles.label}>Target Dialect</Text>
          <View style={styles.pickerContainer}>
            <Picker
              testID="picker"
              selectedValue={dialect}
              onValueChange={(itemValue) => setDialect(itemValue)}
              style={styles.picker}
            >
              <Picker.Item label="Zurich" value="zurich" />
              <Picker.Item label="Bern" value="bern" />
              <Picker.Item label="Basel" value="basel" />
            </Picker>
          </View>
        </View>

        <TouchableOpacity
          style={styles.button}
          onPress={generateAndPlayAudio}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#fff" testID="activity-indicator" />
          ) : (
            <Text style={styles.buttonText}>Speak Dialect</Text>
          )}
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#E6F4FE",
  },
  content: {
    padding: 20,
    flex: 1,
  },
  title: {
    fontSize: 28,
    fontWeight: "bold",
    textAlign: "center",
    marginBottom: 30,
    marginTop: 20,
    color: "#003366",
  },
  section: {
    marginBottom: 20,
  },
  label: {
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 8,
    color: "#333",
  },
  input: {
    backgroundColor: "#fff",
    borderRadius: 10,
    padding: 15,
    fontSize: 16,
    borderWidth: 1,
    borderColor: "#ddd",
    textAlignVertical: "top",
    height: 120,
  },
  pickerContainer: {
    backgroundColor: "#fff",
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#ddd",
    overflow: "hidden",
  },
  picker: {
    height: 50,
    width: "100%",
  },
  button: {
    backgroundColor: "#007AFF",
    padding: 18,
    borderRadius: 12,
    alignItems: "center",
    marginTop: 10,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    minHeight: 60,
    justifyContent: "center",
  },
  buttonText: {
    color: "#fff",
    fontSize: 18,
    fontWeight: "bold",
  },
});
