document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('uploadForm');
    const progress = document.getElementById('progress');
    const result = document.getElementById('result');
    const resultVideo = document.getElementById('resultVideo');
    const downloadBtn = document.getElementById('downloadBtn');
    const wwePreview = document.getElementById('wwePreview');
    const fanPreview = document.getElementById('fanPreview');

    // Handle file selection and preview
    document.querySelectorAll('input[type="file"]').forEach(input => {
        input.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                const preview = e.target.name === 'wwe_video' ? wwePreview : fanPreview;
                const video = preview.querySelector('video');
                video.src = URL.createObjectURL(file);
                preview.classList.remove('hidden');
            }
        });
    });

    // Handle form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(form);
        
        // Show progress bar
        progress.classList.remove('hidden');
        result.classList.add('hidden');
        
        try {
            const response = await fetch('/stitch-videos/', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Failed to process videos');
            }

            // Get the video blob
            const videoBlob = await response.blob();
            const videoUrl = URL.createObjectURL(videoBlob);

            // Display result
            resultVideo.src = videoUrl;
            result.classList.remove('hidden');
            
            // Setup download button
            downloadBtn.href = videoUrl;
            downloadBtn.download = 'stitched_video.mp4';

        } catch (error) {
            alert('Error processing videos: ' + error.message);
        } finally {
            progress.classList.add('hidden');
        }
    });

    // Clean up object URLs when the page is unloaded
    window.addEventListener('beforeunload', () => {
        document.querySelectorAll('video').forEach(video => {
            if (video.src) {
                URL.revokeObjectURL(video.src);
            }
        });
    });
}); 