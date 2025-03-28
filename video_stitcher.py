import cv2
import numpy as np
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip
import os
import logging
import tempfile
import shutil

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoStitcher:
    def __init__(self, wwe_video_path, fan_video_path):
        """
        Initialize the VideoStitcher with paths to input videos
        """
        try:
            # Create a temporary directory for processing
            self.temp_dir = tempfile.mkdtemp()
            logger.info(f"Created temporary directory: {self.temp_dir}")
            
            logger.info(f"Loading WWE video from: {wwe_video_path}")
            self.wwe_video = VideoFileClip(wwe_video_path)
            
            logger.info(f"Loading fan video from: {fan_video_path}")
            self.fan_video = VideoFileClip(fan_video_path)
            
            # Extract audio from fan video
            logger.info("Extracting audio from fan video")
            self.commentary = self.fan_video.audio
            
            # Get frame rates
            self.wwe_fps = self.wwe_video.fps
            self.fan_fps = self.fan_video.fps
            
            # Use the higher frame rate for the final video
            self.target_fps = max(self.wwe_fps, self.fan_fps)
            
            # Ensure all videos are the same size and frame rate
            self.target_size = (1280, 720)  # Reduced resolution for better performance
            logger.info("Resizing videos to target size")
            self.wwe_video = self.wwe_video.resize(self.target_size).set_fps(self.target_fps)
            self.fan_video = self.fan_video.resize(self.target_size).set_fps(self.target_fps)
            
            # Set the duration of the final video
            self.final_duration = 30
            
            # Set transition duration
            self.transition_duration = 0.5  # seconds
            
            # Print video information for debugging
            logger.info(f"WWE Video FPS: {self.wwe_fps}")
            logger.info(f"Fan Video FPS: {self.fan_fps}")
            logger.info(f"Target FPS: {self.target_fps}")
            logger.info(f"WWE Video Duration: {self.wwe_video.duration:.2f} seconds")
            logger.info(f"Fan Video Duration: {self.fan_video.duration:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Error initializing VideoStitcher: {str(e)}")
            self.cleanup()
            raise

    def cleanup(self):
        """Clean up temporary files and resources"""
        try:
            # Close video clips if they exist
            if hasattr(self, 'wwe_video'):
                self.wwe_video.close()
            if hasattr(self, 'fan_video'):
                self.fan_video.close()
            if hasattr(self, 'commentary'):
                self.commentary.close()
            
            # Remove temporary directory if it exists
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info("Cleaned up temporary directory")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    def create_video_segments(self):
        """
        Create video segments according to the specified timing with fade transitions
        """
        try:
            segments = []
            
            # Calculate the duration of each segment
            wwe_duration = self.wwe_video.duration
            fan_duration = self.fan_video.duration
            
            # Define segment timings
            segment_timings = [
                (0, 4, "wwe"),    # 0s - 4s: Intro (WWE video)
                (4, 7, "fan"),    # 4s - 7s: Fan video
                (7, 10, "wwe"),   # 7s - 10s: WWE video
                (10, 13, "fan"),  # 10s - 13s: Fan video
                (13, 22, "wwe"),  # 13s - 22s: WWE video
                (22, 25, "fan"),  # 22s - 25s: Fan video
                (25, 30, "wwe")   # 25s - 30s: Final WWE video
            ]
            
            # Create segments based on timing
            for i, (start_time, end_time, video_type) in enumerate(segment_timings):
                logger.info(f"Creating segment {i+1}: {video_type} video from {start_time}s to {end_time}s")
                if video_type == "wwe":
                    segment = self.wwe_video.subclip(start_time, min(end_time, wwe_duration))
                else:  # fan video
                    segment = self.fan_video.subclip(start_time, min(end_time, fan_duration))
                
                # Ensure consistent frame rate
                segment = segment.set_fps(self.target_fps)
                
                # Add fade in to all segments except the first one
                if i > 0:
                    segment = segment.fadein(self.transition_duration)
                
                # Add fade out to all segments except the last one
                if i < len(segment_timings) - 1:
                    segment = segment.fadeout(self.transition_duration)
                
                segments.append(segment)
            
            # Print segment durations for debugging
            logger.info("\nSegment durations:")
            for i, segment in enumerate(segments):
                logger.info(f"Segment {i}: {segment.duration:.2f} seconds (FPS: {segment.fps})")
            
            return segments
            
        except Exception as e:
            logger.error(f"Error creating video segments: {str(e)}")
            raise

    def stitch_videos(self, output_path):
        """
        Stitch all video segments together with commentary audio
        """
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Create video segments
            logger.info("Creating video segments")
            segments = self.create_video_segments()
            
            # Concatenate all video segments
            logger.info("Concatenating video segments")
            final_video = concatenate_videoclips(segments)
            
            # Ensure final video has correct frame rate
            final_video = final_video.set_fps(self.target_fps)
            
            # Set the commentary audio for the entire duration
            logger.info("Setting commentary audio")
            final_video = final_video.set_audio(self.commentary)
            
            # Print final video information for debugging
            logger.info(f"\nFinal video information:")
            logger.info(f"Duration: {final_video.duration:.2f} seconds")
            logger.info(f"FPS: {final_video.fps}")
            logger.info(f"Size: {final_video.size}")
            
            # Create temporary file path for processing
            temp_output = os.path.join(self.temp_dir, "temp_output.mp4")
            
            # Write the final video with optimized parameters for Render
            logger.info(f"Writing final video to: {temp_output}")
            final_video.write_videofile(
                temp_output,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=os.path.join(self.temp_dir, 'temp-audio.m4a'),
                remove_temp=True,
                fps=self.target_fps,
                threads=1,  # Single thread for better stability
                preset='veryfast',  # Balanced preset for Render
                bitrate='2500k',  # Reduced bitrate for better performance
                audio_bitrate='128k',  # Reduced audio bitrate
                logger=None,  # Disable FFMPEG logging
                ffmpeg_params=['-max_muxing_queue_size', '1024']
            )
            
            # Move the temporary file to the final location
            shutil.move(temp_output, output_path)
            logger.info(f"Moved processed video to: {output_path}")
            
            logger.info("Video processing completed successfully")
            
        except Exception as e:
            logger.error(f"Error stitching videos: {str(e)}")
            raise
        finally:
            # Clean up resources
            self.cleanup()

def main():
    # Example usage
    wwe_video_path = "wwe_video.mp4"  # Replace with your WWE video path
    fan_video_path = "fan_video.mp4"  # Replace with your fan video path
    output_path = "final_video.mp4"
    
    stitcher = VideoStitcher(wwe_video_path, fan_video_path)
    stitcher.stitch_videos(output_path)

if __name__ == "__main__":
    main() 