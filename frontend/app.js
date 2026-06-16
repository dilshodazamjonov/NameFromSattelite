const lettersPage = document.getElementById("lettersPage");
const uploadPage = document.getElementById("uploadPage");
const wordInput = document.getElementById("wordInput");
const generateButton = document.getElementById("generateButton");
const missingWarning = document.getElementById("missingWarning");
const wordOutput = document.getElementById("wordOutput");
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const letterInput = document.getElementById("letterInput");
const placeSelect = document.getElementById("placeSelect");
const noteInput = document.getElementById("noteInput");
const locationInput = document.getElementById("locationInput");
const previewPanel = document.getElementById("previewPanel");
const uploadPreview = document.getElementById("uploadPreview");
const saveButton = document.getElementById("saveButton");
const savedPanel = document.getElementById("savedPanel");
const savedPreview = document.getElementById("savedPreview");
const savedCaption = document.getElementById("savedCaption");
const statusEl = document.getElementById("status");

const API_BASE_URL = getApiBaseUrl();
const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

let selectedFile = null;
let previewObjectUrl = null;

initLetterSelect();
initRoute();
loadPlaces();

window.addEventListener("popstate", initRoute);

generateButton.addEventListener("click", handleGenerateWord);
wordInput.addEventListener("input", () => {
  wordInput.value = wordInput.value.toUpperCase().replace(/[^A-Z]/g, "").slice(0, 7);
});
wordInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    handleGenerateWord();
  }
});

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});
dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("is-dragging");
});
dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("is-dragging");
});
dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("is-dragging");
  const file = imageFileFromFileList(event.dataTransfer.files);
  if (!file) {
    setStatus("Drop an image file.", true);
    return;
  }
  useImageFile(file);
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files && fileInput.files[0];
  if (file) {
    useImageFile(file);
  }
});

window.addEventListener("dragover", (event) => event.preventDefault());
window.addEventListener("drop", (event) => event.preventDefault());
window.addEventListener("paste", (event) => {
  if (!isUploadRoute()) {
    return;
  }
  const item = Array.from(event.clipboardData?.items || []).find((clipboardItem) =>
    clipboardItem.type.startsWith("image/")
  );
  if (!item) {
    return;
  }
  const blob = item.getAsFile();
  if (!blob) {
    setStatus("Clipboard image could not be read.", true);
    return;
  }
  useImageFile(new File([blob], "clipboard_upload.png", { type: blob.type || "image/png" }));
});

saveButton.addEventListener("click", handleSaveLetterImage);

function initRoute() {
  const path = window.location.pathname;
  if (path === "/upload") {
    showUploadPage();
    return;
  }
  showLettersPage();
}

function showLettersPage() {
  lettersPage.classList.remove("hidden");
  uploadPage.classList.add("hidden");
  setStatus("");
}

function showUploadPage() {
  uploadPage.classList.remove("hidden");
  lettersPage.classList.add("hidden");
  setStatus("");
}

function isUploadRoute() {
  return window.location.pathname === "/upload";
}

function initLetterSelect() {
  letterInput.replaceChildren(
    ...LETTERS.map((letter) => {
      const option = document.createElement("option");
      option.value = letter;
      option.textContent = letter;
      return option;
    })
  );
}

async function loadPlaces() {
  try {
    const places = await getPlaces();
    placeSelect.replaceChildren(
      optionElement("", "No place selected"),
      ...places.map((place) => optionElement(place.id, placeLabel(place)))
    );
  } catch {
    placeSelect.replaceChildren(optionElement("", "No place selected"));
  }
}

function useImageFile(file) {
  if (!file.type.startsWith("image/")) {
    setStatus("Choose an image file.", true);
    return;
  }
  selectedFile = file;
  saveButton.disabled = false;
  savedPanel.classList.add("hidden");

  if (previewObjectUrl) {
    URL.revokeObjectURL(previewObjectUrl);
  }
  previewObjectUrl = URL.createObjectURL(file);
  uploadPreview.src = previewObjectUrl;
  previewPanel.classList.remove("hidden");
  setStatus("Image ready. Choose the letter and save it.");
}

async function handleSaveLetterImage() {
  if (!selectedFile) {
    setStatus("Choose an image first.", true);
    return;
  }

  saveButton.disabled = true;
  setStatus("Saving image...");

  const formData = new FormData();
  formData.append("image", selectedFile);
  formData.append("letter", letterInput.value);
  formData.append("note", noteInput.value.trim());
  if (placeSelect.value) {
    formData.append("place_id", placeSelect.value);
  }
  if (locationInput.value.trim()) {
    formData.append("location", locationInput.value.trim());
  }

  try {
    const payload = await uploadLetterImage(formData);
    savedPreview.src = toDisplayUrl(payload.public_url);
    savedCaption.textContent = payload.location
      ? `Saved as ${payload.letter} at ${payload.location}: ${payload.storage_key}`
      : `Saved as ${payload.letter}: ${payload.storage_key}`;
    savedPanel.classList.remove("hidden");
    setStatus("Saved. You can add another image or generate a word.");
    resetUploadFormAfterSave();
    loadPlaces();
  } catch (error) {
    saveButton.disabled = false;
    setStatus(error.message, true);
  } finally {
    fileInput.value = "";
  }
}

function resetUploadFormAfterSave() {
  selectedFile = null;
  saveButton.disabled = true;
  previewPanel.classList.add("hidden");
  uploadPreview.removeAttribute("src");
  noteInput.value = "";
  locationInput.value = "";
  if (previewObjectUrl) {
    URL.revokeObjectURL(previewObjectUrl);
    previewObjectUrl = null;
  }
}

async function handleGenerateWord() {
  const word = wordInput.value.trim().toUpperCase();
  if (!/^[A-Z]{1,7}$/.test(word)) {
    setStatus("Enter 1-7 English letters A-Z.", true);
    return;
  }

  setStatus("Generating word...");
  missingWarning.classList.add("hidden");
  wordOutput.replaceChildren();

  try {
    const payload = await generateWord(word);
    renderGeneratedWord(payload);
    setStatus(payload.status === "complete" ? "Generated word." : "Generated partial word.");
  } catch (error) {
    setStatus(error.message, true);
  }
}

function renderGeneratedWord(payload) {
  if (payload.missing_letters.length) {
    missingWarning.textContent = `Missing images for: ${payload.missing_letters.join(", ")}`;
    missingWarning.classList.remove("hidden");
  }

  wordOutput.replaceChildren(
    ...payload.letters.map((item) => {
      const tile = document.createElement("figure");
      tile.className = "letter-tile";

      const label = document.createElement("figcaption");
      label.textContent = item.letter;

      const image = document.createElement("img");
      image.src = toDisplayUrl(item.public_url);
      image.alt = `Saved satellite letter ${item.letter}`;

      const mapUrl = googleMapsUrl(item.latitude, item.longitude);
      if (mapUrl) {
        const imageLink = document.createElement("a");
        imageLink.className = "image-map-link";
        imageLink.href = mapUrl;
        imageLink.target = "_blank";
        imageLink.rel = "noopener noreferrer";
        imageLink.append(image);
        tile.append(label, imageLink);
      } else {
        tile.append(label, image);
      }
      if (item.location) {
        const location = document.createElement("span");
        location.className = "tile-location";
        location.textContent = item.location;
        tile.append(location);
      }
      if (mapUrl) {
        const mapLink = document.createElement("a");
        mapLink.className = "map-link";
        mapLink.href = mapUrl;
        mapLink.target = "_blank";
        mapLink.rel = "noopener noreferrer";
        mapLink.textContent = "Open map";
        tile.append(mapLink);
      }
      return tile;
    })
  );
}

async function generateWord(word) {
  return postJson("/api/words/generate", { word });
}

async function uploadLetterImage(formData) {
  const response = await fetch(`${API_BASE_URL}/api/letters/images`, {
    method: "POST",
    body: formData,
  });
  return parseApiResponse(response, "Save failed.");
}

async function getPlaces() {
  const response = await fetch(`${API_BASE_URL}/api/places`);
  return parseApiResponse(response, "Could not load places.");
}

async function getLetterImages(filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  const suffix = params.toString() ? `?${params}` : "";
  const response = await fetch(`${API_BASE_URL}/api/letters/images${suffix}`);
  return parseApiResponse(response, "Could not load letter images.");
}

async function postJson(path, body) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseApiResponse(response, "Request failed.");
}

async function parseApiResponse(response, fallbackMessage) {
  const text = await response.text();
  const payload = text ? safeJson(text) : {};
  if (!response.ok) {
    throw new Error(payload.detail || fallbackMessage);
  }
  return payload;
}

function safeJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text.slice(0, 160) };
  }
}

function getApiBaseUrl() {
  const configured =
    window.VITE_API_BASE_URL ||
    window.NEXT_PUBLIC_API_BASE_URL ||
    window.__API_BASE_URL__ ||
    document.querySelector("meta[name='api-base-url']")?.getAttribute("content") ||
    "";
  if (configured) {
    return configured.replace(/\/$/, "");
  }

  const isLocalhost = window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost";
  const liveServerPorts = new Set(["5500", "5501"]);
  if (isLocalhost && liveServerPorts.has(window.location.port)) {
    return "http://localhost:8000";
  }
  return "";
}

function toDisplayUrl(publicUrl) {
  if (!publicUrl || publicUrl.startsWith("http://") || publicUrl.startsWith("https://") || !API_BASE_URL) {
    return publicUrl;
  }
  return `${API_BASE_URL}${publicUrl}`;
}

function googleMapsUrl(latitude, longitude) {
  const lat = Number(latitude);
  const lon = Number(longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    return null;
  }
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
    return null;
  }
  return `https://www.google.com/maps?q=${lat},${lon}`;
}

function optionElement(value, label) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  return option;
}

function placeLabel(place) {
  const parts = [place.name, place.city, place.region].filter(Boolean);
  return [...new Set(parts)].join(" - ") || place.id;
}

function imageFileFromFileList(fileList) {
  return Array.from(fileList || []).find((item) => item.type.startsWith("image/"));
}

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}
