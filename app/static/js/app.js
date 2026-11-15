
document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("generationForm");

    if (!form) {
        console.error("Generation form not found.");
        return;
    }

    // Create the generation status area.
    const statusArea = document.createElement("div");
    statusArea.id = "generationStatus";
    statusArea.style.marginTop = "20px";
    form.insertAdjacentElement("afterend", statusArea);

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const formData = new FormData(form);
        const button = form.querySelector('button[type="submit"]');

        if (!formData.get("image")?.name || !formData.get("audio")?.name) {
            statusArea.textContent = "Please select both an image and an audio file.";
            return;
        }

        button.disabled = true;
        button.textContent = "Uploading...";

        statusArea.textContent = "Uploading your files...";

        try {
            const response = await fetch("/api/generate", {
                method: "POST",
                body: formData
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.message || "Upload failed.");
            }

            statusArea.textContent = "Upload successful. Waiting for generation...";
            await monitorGeneration(result.job_id);

        } catch (error) {
            console.error("Generation error:", error);
            statusArea.textContent = error.message;

        } finally {
            button.disabled = false;
            button.textContent = "Generate Talking Video";
        }
    });

    async function monitorGeneration(jobId) {
        while (true) {
            const response = await fetch(`/api/status/${jobId}`);
            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.message || "Unable to check generation status.");
            }

            statusArea.textContent = result.message;

            if (result.status === "completed") {
                displayVideo(result.video_url);
                return;
            }

            if (result.status === "failed") {
                throw new Error(result.message || "Video generation failed.");
            }

            await new Promise(resolve => setTimeout(resolve, 3000));
        }
    }

    function displayVideo(videoUrl) {
        statusArea.innerHTML = `
            <h3>Video generation completed!</h3>

            <video
                controls
                style="width: 100%; max-width: 600px; border-radius: 10px;"
            >
                <source src="${videoUrl}" type="video/mp4">
                Your browser does not support video playback.
            </video>

            <p>
                <a href="${videoUrl}" download="talking-video.mp4">
                    Download Talking Video
                </a>
            </p>
        `;
    }
});
