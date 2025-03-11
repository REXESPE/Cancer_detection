import React, { useState, useRef } from "react";
import axios from "axios";

const App = () => {
  const [image, setImage] = useState(null);
  const [results, setResults] = useState(null);
  const canvasRef = useRef(null);

  const handleUpload = (e) => {
    const file = e.target.files[0];
    setVideo(file); // Cambia 'image' por 'video'
  };
  
  const handleSubmit = async () => {
    const formData = new FormData();
    formData.append("video", video);
  
    const response = await axios.post("  http://127.0.0.1:8080", formData, {
      responseType: "blob", // Importante para manejar archivos binarios
    });
  
    const videoURL = URL.createObjectURL(new Blob([response.data]));
    setProcessedVideo(videoURL); // Mostrar el video procesado en el cliente
      };
    };
    reader.readAsDataURL(file);


  const handleSubmit = async () => {
    const formData = new FormData();
    formData.append("image", image);

    const response = await axios.post("http://127.0.0.1:5000/ ", formData);
    const data = response.data;


    setResults(data);

    // Dibujar los resultados en el canvas
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    ctx.strokeStyle = "red";
    ctx.lineWidth = 2;
    data.boxes.forEach((box, index) => {
      const [x1, y1, x2, y2] = box;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

      ctx.fillStyle = "red";
      ctx.font = "16px Arial";
      ctx.fillText(
        `${data.classes[index]}: ${Math.round(data.scores[index] * 100)}%`,
        x1,
        y1 - 5
      );
    });
  };

  return (
    <div>
      <h1>YOLOv8 Object Detection</h1>
      <input type="file" accept="image/*" onChange={handleUpload} />
      <button onClick={handleSubmit}>Predict</button>
      <canvas ref={canvasRef} style={{ border: "1px solid black" }} />
    </div>
  );

export default App;
