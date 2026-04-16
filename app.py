import os
import time
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
ASSET_FOLDER = "assets"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


@app.route("/")
def home():
    return "Backend Running ✅"

@app.route("/upload", methods=["POST"])
def upload():

    from moviepy.editor import (
        VideoFileClip,
        AudioFileClip,
        ImageClip,
        CompositeVideoClip,
        concatenate_videoclips,
        VideoClip
    )
    from rembg import remove
    from PIL import Image, ImageFilter
    import numpy as np

    # ✅ FIX 1: get file properly
    if "video" not in request.files:
        return jsonify({"error": "No video file sent"}), 400

    file = request.files["video"]

    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    input_path = os.path.join(UPLOAD_FOLDER, file.filename)

    filename = f"reel_{int(time.time())}.mp4"
    output_path = os.path.join(OUTPUT_FOLDER, filename)

    file.save(input_path)

    try:
        print("Processing video...")

        clip = VideoFileClip(input_path)

        total_duration = 14

        part1 = clip.subclip(0, min(4, clip.duration))
        part1 = part1.resize((720, 1280))

        part2_duration = total_duration - part1.duration

        frame = clip.get_frame(min(4, clip.duration - 0.1))
        img = Image.fromarray(frame)

        cutout = remove(img)
        cutout_np = np.array(cutout)

        cutout_pil = Image.fromarray(cutout_np)
        mask = cutout_pil.split()[-1]

        stroke_mask = mask.filter(ImageFilter.MaxFilter(15))

        stroke_img = Image.new("RGBA", cutout_pil.size, (255, 255, 255, 0))
        stroke_img.putalpha(stroke_mask)

        combined = Image.alpha_composite(stroke_img, cutout_pil)
        final_img = np.array(combined)

        freeze = ImageClip(final_img).set_duration(part2_duration)
        freeze = freeze.resize(height=850)

        bg = VideoFileClip(os.path.join(ASSET_FOLDER, "bg.mp4"))
        bg = bg.loop(duration=part2_duration)
        bg = bg.resize((720, 1280))

        W, H = 720, 1280
        open_time = 6

        def make_frame(t):
            frame = np.zeros((H, W, 1), dtype=float)

            if t < open_time:
                progress = t / open_time
                progress = 1 - (1 - progress) ** 3

                center = H // 2
                offset = int((H // 2) * progress)

                frame[center - offset:center + offset, :, 0] = 1
            else:
                frame[:, :, 0] = 1

            return frame

        mask_clip = VideoClip(make_frame=make_frame, duration=part2_duration).set_fps(24)
        mask_clip = mask_clip.set_ismask(True)

        bg = bg.set_mask(mask_clip)

        part2 = CompositeVideoClip([bg, freeze], size=(720, 1280))
        part2 = part2.set_duration(part2_duration)

        final = concatenate_videoclips([part1, part2])

        audio = AudioFileClip(os.path.join(ASSET_FOLDER, "music.mp3"))
        audio = audio.subclip(0, final.duration)

        final = final.set_audio(audio)

        final.write_videofile(output_path, fps=24)

        return jsonify({
            "url": request.host_url + "download/" + filename
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route("/download/<filename>")
def download(filename):
    return send_file(os.path.join(OUTPUT_FOLDER, filename), as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)