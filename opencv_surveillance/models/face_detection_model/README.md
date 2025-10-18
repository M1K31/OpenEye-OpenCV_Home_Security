# Face Detection Models

## OpenCV DNN Face Detector

These models provide an alternative face detection method using OpenCV's Deep Neural Network module.

### Files

- **deploy.prototxt** - Network architecture definition (28 KB)
- **res10_300x300_ssd_iter_140000.caffemodel** - Pre-trained weights (10.7 MB)

### About

- **Model Type**: Single Shot Detector (SSD)
- **Framework**: Caffe
- **Input Size**: 300x300 pixels
- **Accuracy**: Better than HOG, competitive with dlib CNN
- **Speed**: Faster than dlib CNN on most hardware

### Usage

```python
import cv2

# Load the model
net = cv2.dnn.readNetFromCaffe(
    'deploy.prototxt',
    'res10_300x300_ssd_iter_140000.caffemodel'
)

# Detect faces
blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), (104.0, 177.0, 123.0))
net.setInput(blob)
detections = net.forward()
```

### Comparison with Other Methods

| Method | Accuracy | Speed | Use Case |
|--------|----------|-------|----------|
| HOG (dlib) | Good | Fast | Real-time, frontal faces |
| DNN (OpenCV) | Better | Medium | Balanced accuracy/speed |
| CNN (dlib) | Best | Slow | High accuracy needed |

### Source

Downloaded from OpenCV official repositories:
- Architecture: https://github.com/opencv/opencv/tree/master/samples/dnn/face_detector
- Weights: https://github.com/opencv/opencv_3rdparty/tree/dnn_samples_face_detector_20170830

### License

These models are provided under the OpenCV license for research and commercial use.
