// ---------------------------------------------------------------------------
// Environment variable - MUST be set before importing App
// ---------------------------------------------------------------------------
const MOCK_API_IP = "192.168.1.100"; //NOSONAR

// Set environment variable before any imports
process.env.EXPO_PUBLIC_API_IP = MOCK_API_IP;

// Import after setting environment variable
const React = require("react");
const {
  render,
  fireEvent,
  waitFor,
  act,
} = require("@testing-library/react-native");
const { Alert } = require("react-native");
const App = require("../App").default;

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

// Mock expo-av Audio
const mockUnloadAsync = jest.fn().mockResolvedValue(undefined);
const mockCreateAsync = jest.fn();

jest.mock("expo-av", () => ({
  Audio: {
    Sound: {
      createAsync: (...args) => mockCreateAsync(...args),
    },
  },
}));

// Mock @react-native-picker/picker – render as a simple passthrough View
// that exposes the onValueChange callback via a testable prop.
jest.mock("@react-native-picker/picker", () => {
  const React = require("react");
  const { View } = require("react-native");

  const Picker = ({
    children,
    onValueChange,
    selectedValue,
    testID,
    ...rest
  }) =>
    React.createElement(
      View,
      { testID: testID || "picker", onValueChange, selectedValue, ...rest },
      children,
    );

  Picker.Item = ({ label, value }) => null;

  return { Picker };
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a minimal fetch Response-like object. */
function makeFetchResponse({ ok, status, json }) {
  return {
    ok,
    status,
    json: jest.fn().mockResolvedValue(json),
  };
}

// ---------------------------------------------------------------------------
// Test setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  jest.clearAllMocks();
  jest.spyOn(Alert, "alert").mockImplementation(() => {});

  // Default: successful fetch response
  globalThis.fetch = jest.fn().mockResolvedValue(
    makeFetchResponse({
      ok: true,
      status: 200,
      json: { audio_url: "/audio/test.wav" },
    }),
  );

  // Default: successful Audio creation
  mockCreateAsync.mockResolvedValue({
    sound: { unloadAsync: mockUnloadAsync },
  });
});

afterEach(() => {
  jest.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Rendering / initial state
// ---------------------------------------------------------------------------

describe("App rendering", () => {
  it("renders the app title", () => {
    const { getByText } = render(<App />);
    expect(getByText("🇨🇭 Swiss TTS Mobile")).toBeTruthy();
  });

  it("renders the TextInput with the default placeholder text", () => {
    const { getByDisplayValue } = render(<App />);
    expect(
      getByDisplayValue("Guten Tag, mein Name ist Abhay Singh."),
    ).toBeTruthy();
  });

  it('renders the "Speak Dialect" button when not loading', () => {
    const { getByText } = render(<App />);
    expect(getByText("Speak Dialect")).toBeTruthy();
  });

  it("renders the section labels", () => {
    const { getByText } = render(<App />);
    expect(getByText("Input Text (Any Language)")).toBeTruthy();
    expect(getByText("Target Dialect")).toBeTruthy();
  });

  it("does not show ActivityIndicator on initial render", () => {
    const { queryByTestId, getByText } = render(<App />);
    // ActivityIndicator has no testID by default; ensure the button exists as a proxy
    expect(queryByTestId("activity-indicator")).toBeFalsy();
    expect(getByText("Speak Dialect")).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Input validation
// ---------------------------------------------------------------------------

describe("generateAndPlayAudio – input validation", () => {
  it('shows "Input Required" alert when text is empty', async () => {
    const { getByDisplayValue, getByText } = render(<App />);

    // Clear the text input
    fireEvent.changeText(
      getByDisplayValue("Guten Tag, mein Name ist Abhay Singh."),
      "",
    );

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).toHaveBeenCalledWith(
      "Input Required",
      "Please enter some text to synthesize.",
    );
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it('shows "Input Required" alert when text contains only whitespace', async () => {
    const { getByDisplayValue, getByText } = render(<App />);

    fireEvent.changeText(
      getByDisplayValue("Guten Tag, mein Name ist Abhay Singh."),
      "   ",
    );

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).toHaveBeenCalledWith(
      "Input Required",
      "Please enter some text to synthesize.",
    );
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("does not show an alert and proceeds with fetch when text is valid", async () => {
    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).not.toHaveBeenCalledWith(
      "Input Required",
      expect.any(String),
    );
    expect(globalThis.fetch).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Successful audio generation
// ---------------------------------------------------------------------------

describe("generateAndPlayAudio – success path", () => {
  it("sends a POST to the correct endpoint with text and dialect", async () => {
    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      `http://${MOCK_API_IP}:8000/api/v1/synthesize`,
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: "Guten Tag, mein Name ist Abhay Singh.",
          dialect: "zurich",
        }),
      }),
    );
  });

  it("calls Audio.Sound.createAsync with the constructed audio URL", async () => {
    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    await waitFor(() => {
      expect(mockCreateAsync).toHaveBeenCalled();
    });

    const [audioConfig, options] = mockCreateAsync.mock.calls[0];

    expect(audioConfig).toEqual(
      expect.objectContaining({
        uri: expect.stringMatching(
          new RegExp(`^http://${MOCK_API_IP}:8000/audio/test\\.wav\\?t=\\d+$`), //NOSONAR
        ),
      }),
    );

    expect(options).toEqual({
      shouldPlay: true,
    });
  });

  it("includes a cache-busting timestamp in the audio URL", async () => {
    const fixedTime = 1700000000000;
    jest.spyOn(Date, "now").mockReturnValue(fixedTime);

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(mockCreateAsync).toHaveBeenCalledWith(
      { uri: `http://${MOCK_API_IP}:8000/audio/test.wav?t=${fixedTime}` },
      { shouldPlay: true },
    );
  });

  it("does not show an error alert on successful synthesis", async () => {
    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// HTTP error handling
// ---------------------------------------------------------------------------

describe("generateAndPlayAudio – HTTP error handling", () => {
  it("shows server error message for 5xx responses", async () => {
    globalThis.fetch = jest
      .fn()
      .mockResolvedValue(
        makeFetchResponse({ ok: false, status: 503, json: {} }),
      );

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).toHaveBeenCalledWith(
      "Error",
      "Server error (503). The service may be temporarily unavailable.",
    );
  });

  it("shows server error message for 500 responses", async () => {
    globalThis.fetch = jest
      .fn()
      .mockResolvedValue(
        makeFetchResponse({ ok: false, status: 500, json: {} }),
      );

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).toHaveBeenCalledWith(
      "Error",
      "Server error (500). The service may be temporarily unavailable.",
    );
  });

  it("shows client error message for 4xx responses", async () => {
    globalThis.fetch = jest
      .fn()
      .mockResolvedValue(
        makeFetchResponse({ ok: false, status: 422, json: {} }),
      );

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).toHaveBeenCalledWith(
      "Error",
      "Request error (422). Please check your input and try again.",
    );
  });

  it("shows client error message for 400 responses", async () => {
    globalThis.fetch = jest
      .fn()
      .mockResolvedValue(
        makeFetchResponse({ ok: false, status: 400, json: {} }),
      );

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).toHaveBeenCalledWith(
      "Error",
      "Request error (400). Please check your input and try again.",
    );
  });

  it("shows generic HTTP error message for non-4xx/5xx error codes", async () => {
    globalThis.fetch = jest
      .fn()
      .mockResolvedValue(
        makeFetchResponse({ ok: false, status: 301, json: {} }),
      );

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).toHaveBeenCalledWith(
      "Error",
      "HTTP error (301). Please try again.",
    );
  });
});

// ---------------------------------------------------------------------------
// JSON parse error
// ---------------------------------------------------------------------------

describe("generateAndPlayAudio – JSON parse error", () => {
  it("shows invalid response message when JSON parsing fails", async () => {
    const badResponse = {
      ok: true,
      status: 200,
      json: jest.fn().mockRejectedValue(new SyntaxError("Unexpected token")),
    };
    globalThis.fetch = jest.fn().mockResolvedValue(badResponse);

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).toHaveBeenCalledWith(
      "Error",
      "Server returned an invalid response. Please try again.",
    );
  });
});

// ---------------------------------------------------------------------------
// Audio playback error
// ---------------------------------------------------------------------------

describe("generateAndPlayAudio – audio playback error", () => {
  it("shows audio playback error message when Audio.Sound.createAsync throws", async () => {
    mockCreateAsync.mockRejectedValue(new Error("Could not load audio"));

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).toHaveBeenCalledWith(
      "Error",
      "Failed to load or play the audio file. Please check your connection and try again.",
    );
  });
});

// ---------------------------------------------------------------------------
// Network errors
// ---------------------------------------------------------------------------

describe("generateAndPlayAudio – network errors", () => {
  it("shows a generic error if the API IP disappears before audio playback", async () => {
    const previousApiIp = process.env.EXPO_PUBLIC_API_IP;
    try {
      delete process.env.EXPO_PUBLIC_API_IP;

      const { getByText } = render(<App />);

      await act(async () => {
        fireEvent.press(getByText("Speak Dialect"));
      });

      expect(Alert.alert).toHaveBeenCalledWith(
        "Error",
        "An unexpected error occurred.",
      );
      expect(mockCreateAsync).not.toHaveBeenCalled();
    } finally {
      process.env.EXPO_PUBLIC_API_IP = previousApiIp;
    }
  });

  it('shows network error message when fetch throws "Network request failed"', async () => {
    const networkError = new Error("Network request failed");
    globalThis.fetch = jest.fn().mockRejectedValue(networkError);

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).toHaveBeenCalledWith(
      "Error",
      "Network connection failed. Ensure Docker is running and your API IP is configured correctly.",
    );
  });

  it("shows network error message when fetch throws a TypeError", async () => {
    const typeError = new TypeError("Failed to fetch");
    globalThis.fetch = jest.fn().mockRejectedValue(typeError);

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).toHaveBeenCalledWith(
      "Error",
      "Network connection failed. Ensure Docker is running and your API IP is configured correctly.",
    );
  });

  it("shows generic unexpected error message for unknown errors", async () => {
    const unknownError = new Error("Something completely unexpected");
    globalThis.fetch = jest.fn().mockRejectedValue(unknownError);

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).toHaveBeenCalledWith(
      "Error",
      "An unexpected error occurred.",
    );
  });
});

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

describe("generateAndPlayAudio – loading state", () => {
  it("resets loading to false after a successful request", async () => {
    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    // Button should be visible again after loading finishes
    await waitFor(() => {
      expect(getByText("Speak Dialect")).toBeTruthy();
    });
  });

  it("resets loading to false even when an error occurs", async () => {
    globalThis.fetch = jest
      .fn()
      .mockRejectedValue(new Error("Network request failed"));

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    await waitFor(() => {
      expect(getByText("Speak Dialect")).toBeTruthy();
    });
  });
});

// ---------------------------------------------------------------------------
// Sound resource management
// ---------------------------------------------------------------------------

describe("generateAndPlayAudio – sound resource management", () => {
  it("unloads a previously loaded sound before creating a new one", async () => {
    const firstSoundMock = {
      unloadAsync: jest.fn().mockResolvedValue(undefined),
    };
    const secondSoundMock = {
      unloadAsync: jest.fn().mockResolvedValue(undefined),
    };

    // First call returns firstSoundMock; second returns secondSoundMock
    mockCreateAsync
      .mockResolvedValueOnce({ sound: firstSoundMock })
      .mockResolvedValueOnce({ sound: secondSoundMock });

    const { getByText } = render(<App />);

    // First press – loads firstSoundMock
    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(firstSoundMock.unloadAsync).not.toHaveBeenCalled();

    // Second press – should unload first sound before loading second
    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(firstSoundMock.unloadAsync).toHaveBeenCalled();
  });

  it("calls unloadAsync on the active sound when the component unmounts", async () => {
    const soundMock = { unloadAsync: jest.fn().mockResolvedValue(undefined) };
    mockCreateAsync.mockResolvedValueOnce({ sound: soundMock });

    const { getByText, unmount } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(soundMock.unloadAsync).not.toHaveBeenCalled();

    unmount();

    expect(soundMock.unloadAsync).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Text and dialect state
// ---------------------------------------------------------------------------

describe("App state management", () => {
  it("updates text state when the TextInput value changes", async () => {
    const { getByDisplayValue } = render(<App />);
    const input = getByDisplayValue("Guten Tag, mein Name ist Abhay Singh.");

    fireEvent.changeText(input, "Hello, world!");

    expect(getByDisplayValue("Hello, world!")).toBeTruthy();
  });

  it("sends the updated text to the API after text input change", async () => {
    const { getByDisplayValue, getByText } = render(<App />);

    fireEvent.changeText(
      getByDisplayValue("Guten Tag, mein Name ist Abhay Singh."),
      "Wie geht es Ihnen?",
    );

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: JSON.stringify({ text: "Wie geht es Ihnen?", dialect: "zurich" }),
      }),
    );
  });

  it('uses the default dialect "zurich" in the request', async () => {
    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: expect.stringContaining('"dialect":"zurich"'),
      }),
    );
  });

  it("sends the selected dialect to the API after Picker value changes", async () => {
    const { getByTestId, getByText } = render(<App />);

    // Simulate the Picker's onValueChange firing with "bern"
    const picker = getByTestId("picker");
    fireEvent(picker, "onValueChange", "bern");

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: JSON.stringify({
          text: "Guten Tag, mein Name ist Abhay Singh.",
          dialect: "bern",
        }),
      }),
    );
  });

  it("sends the selected dialect to the API when switching to basel", async () => {
    const { getByTestId, getByText } = render(<App />);

    const picker = getByTestId("picker");
    fireEvent(picker, "onValueChange", "basel");

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: JSON.stringify({
          text: "Guten Tag, mein Name ist Abhay Singh.",
          dialect: "basel",
        }),
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// Boundary / regression tests
// ---------------------------------------------------------------------------

describe("generateAndPlayAudio – boundary and regression cases", () => {
  it("treats a single space as invalid (whitespace-only) input", async () => {
    const { getByDisplayValue, getByText } = render(<App />);

    fireEvent.changeText(
      getByDisplayValue("Guten Tag, mein Name ist Abhay Singh."),
      " ",
    );

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).toHaveBeenCalledWith(
      "Input Required",
      "Please enter some text to synthesize.",
    );
  });

  it("handles a 404 response as a client error (4xx)", async () => {
    globalThis.fetch = jest
      .fn()
      .mockResolvedValue(
        makeFetchResponse({ ok: false, status: 404, json: {} }),
      );

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).toHaveBeenCalledWith(
      "Error",
      "Request error (404). Please check your input and try again.",
    );
  });

  it("does not call Audio.Sound.createAsync when the HTTP response is not ok", async () => {
    globalThis.fetch = jest
      .fn()
      .mockResolvedValue(
        makeFetchResponse({ ok: false, status: 500, json: {} }),
      );

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(mockCreateAsync).not.toHaveBeenCalled();
  });

  it("does not call Audio.Sound.createAsync when JSON parsing fails", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: jest.fn().mockRejectedValue(new SyntaxError("bad json")),
    });

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(mockCreateAsync).not.toHaveBeenCalled();
  });

  it("shows only one alert per failed request", async () => {
    globalThis.fetch = jest
      .fn()
      .mockRejectedValue(new Error("Network request failed"));

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// Additional coverage tests
// ---------------------------------------------------------------------------

describe("Additional App coverage", () => {
  it("throws during module load when EXPO_PUBLIC_API_IP is not configured", () => {
    const previousApiIp = process.env.EXPO_PUBLIC_API_IP;
    delete process.env.EXPO_PUBLIC_API_IP;

    jest.isolateModules(() => {
      expect(() => {
        require("../App");
      }).toThrow(
        "EXPO_PUBLIC_API_IP environment variable is not defined. Please configure it in your .env file.",
      );
    });

    process.env.EXPO_PUBLIC_API_IP = previousApiIp;
  });

  it("shows ActivityIndicator while a request is pending", async () => {
    let resolveFetch;

    globalThis.fetch = jest.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        }),
    );

    const { getByText, queryByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    // Button should disappear while loading
    expect(queryByText("Speak Dialect")).toBeFalsy();

    await act(async () => {
      resolveFetch(
        makeFetchResponse({
          ok: true,
          status: 200,
          json: { audio_url: "/audio/loading.wav" },
        }),
      );
    });

    await waitFor(() => {
      expect(getByText("Speak Dialect")).toBeTruthy();
    });
  });

  it("cleans up previous sound before attempting a second playback", async () => {
    const oldSound = {
      unloadAsync: jest.fn().mockResolvedValue(undefined),
    };

    mockCreateAsync
      .mockResolvedValueOnce({ sound: oldSound })
      .mockRejectedValueOnce(new Error("audio failed"));

    const { getByText } = render(<App />);

    // First synthesis
    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    // Second synthesis
    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(oldSound.unloadAsync).toHaveBeenCalled();

    expect(Alert.alert).toHaveBeenCalledWith(
      "Error",
      "Failed to load or play the audio file. Please check your connection and try again.",
    );
  });

  it("handles API response without audio_url", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: jest.fn().mockResolvedValue({}),
    });

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(mockCreateAsync).toHaveBeenCalledWith(
      {
        uri: expect.stringContaining("undefined"),
      },
      {
        shouldPlay: true,
      },
    );

    expect(Alert.alert).not.toHaveBeenCalled();
  });

  it("handles HTTP status 0 failures", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue(
      makeFetchResponse({
        ok: false,
        status: 0,
        json: {},
      }),
    );

    const { getByText } = render(<App />);

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(Alert.alert).toHaveBeenCalledWith(
      "Error",
      "HTTP error (0). Please try again.",
    );
  });

  it("supports large text input payloads", async () => {
    const longText = "Swiss German translation test ".repeat(100);

    const { getByDisplayValue, getByText } = render(<App />);

    fireEvent.changeText(
      getByDisplayValue("Guten Tag, mein Name ist Abhay Singh."),
      longText,
    );

    expect(getByDisplayValue(longText)).toBeTruthy();

    await act(async () => {
      fireEvent.press(getByText("Speak Dialect"));
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: JSON.stringify({
          text: longText,
          dialect: "zurich",
        }),
      }),
    );
  });
});
