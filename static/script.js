document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('uploadForm');
    const progress = document.getElementById('progress');
    const result = document.getElementById('result');
    const resultVideo = document.getElementById('resultVideo');
    const downloadBtn = document.getElementById('downloadBtn');
    const wwePreview = document.getElementById('wwePreview');
    const fanPreview = document.getElementById('fanPreview');
    const recentVideos = document.getElementById('recentVideos');
    const popularVideos = document.getElementById('popularVideos');

    // Load recent and popular videos
    loadRecentVideos();
    loadPopularVideos();

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
            const response = await fetch('/api/v1/stitch', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Failed to process videos');
            }

            const task = await response.json();
            
            // Poll for task completion
            await pollTaskStatus(task.id);
            
            // Get the video blob
            const videoResponse = await fetch(`/api/v1/tasks/${task.id}/download`);
            const videoBlob = await videoResponse.blob();
            const videoUrl = URL.createObjectURL(videoBlob);

            // Display result
            resultVideo.src = videoUrl;
            result.classList.remove('hidden');
            
            // Setup download button
            downloadBtn.href = videoUrl;
            downloadBtn.download = 'stitched_video.mp4';

            // Reload recent videos
            loadRecentVideos();
            loadPopularVideos();

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

    // Helper function to poll task status
    async function pollTaskStatus(taskId) {
        const maxAttempts = 60; // 5 minutes with 5-second intervals
        let attempts = 0;

        while (attempts < maxAttempts) {
            const response = await fetch(`/api/v1/tasks/${taskId}`);
            const task = await response.json();

            if (task.status === 'completed') {
                return;
            } else if (task.status === 'failed') {
                throw new Error(task.error || 'Task failed');
            }

            // Update progress bar
            const progressBar = progress.querySelector('.progress-bar');
            const progressPercent = Math.min((attempts / maxAttempts) * 100, 95);
            progressBar.style.width = `${progressPercent}%`;

            await new Promise(resolve => setTimeout(resolve, 5000));
            attempts++;
        }

        throw new Error('Task timed out');
    }

    // Load recent videos
    async function loadRecentVideos() {
        try {
            const response = await fetch('/api/v1/downloads/recent');
            const videos = await response.json();
            
            recentVideos.innerHTML = videos.map(video => `
                <div class="bg-white p-4 rounded-lg shadow">
                    <h3 class="text-sm font-medium text-gray-900">${video.filename}</h3>
                    <p class="text-xs text-gray-500">${new Date(video.timestamp * 1000).toLocaleString()}</p>
                    <a href="/api/v1/tasks/${video.task_id}/download" 
                       class="mt-2 inline-flex items-center px-3 py-1 border border-transparent text-xs font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700">
                        Download
                    </a>
                </div>
            `).join('');
        } catch (error) {
            console.error('Error loading recent videos:', error);
        }
    }

    // Load popular videos
    async function loadPopularVideos() {
        try {
            const response = await fetch('/api/v1/downloads/popular');
            const videos = await response.json();
            
            popularVideos.innerHTML = videos.map(video => `
                <div class="bg-white p-4 rounded-lg shadow">
                    <h3 class="text-sm font-medium text-gray-900">${video.output_filename}</h3>
                    <p class="text-xs text-gray-500">Downloads: ${video.downloads}</p>
                    <a href="/api/v1/tasks/${video.id}/download" 
                       class="mt-2 inline-flex items-center px-3 py-1 border border-transparent text-xs font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700">
                        Download
                    </a>
                </div>
            `).join('');
        } catch (error) {
            console.error('Error loading popular videos:', error);
        }
    }
}); 