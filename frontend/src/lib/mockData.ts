/** Realistic mock data for demonstrating all UI screens. */

export const MOCK_NOTES = {
  content_type: 'educational' as const,
  language_detected: 'en',
  has_audio: true,
  title: 'Introduction to Gradient Descent',
  tldr: 'Gradient descent is the core optimization algorithm behind neural network training. This video explains how it minimizes a loss function by iteratively stepping in the direction of steepest descent, covering learning rates, momentum, and common pitfalls like vanishing gradients.',
  main_topics: [
    'Loss Functions',
    'Gradient Descent',
    'Learning Rate',
    'Backpropagation',
    'Vanishing Gradients',
    'Adam Optimizer',
  ],
  key_concepts: [
    {
      concept: 'Gradient Descent',
      explanation:
        'An iterative optimization algorithm that updates model parameters in the direction of the negative gradient of the loss function. The update rule is: θ = θ − α ∇L(θ), where α is the learning rate.',
    },
    {
      concept: 'Learning Rate',
      explanation:
        'Controls the size of each optimization step. Too large and training diverges; too small and convergence is painfully slow. Adaptive methods like Adam adjust the learning rate per-parameter.',
    },
    {
      concept: 'Vanishing Gradients',
      explanation:
        'Occurs in deep networks when gradients shrink exponentially as they propagate backward. Makes early layers learn extremely slowly. Addressed by ReLU activations, skip connections, and batch normalization.',
    },
    {
      concept: 'Momentum',
      explanation:
        'Accumulates a velocity vector in the gradient direction, dampening oscillations and accelerating convergence in consistent directions. Hyperparameter β typically set to 0.9.',
    },
  ],
  detailed_notes: `## Overview

Gradient descent is the fundamental algorithm used to train nearly all modern neural networks. At its core, it answers the question: *given a loss function, how do we find the parameters that minimize it?*

## The Loss Landscape

The loss function L(θ) maps model parameters θ to a scalar value representing prediction error. Training is equivalent to finding the lowest point in this high-dimensional landscape.

- **Convex problems** (e.g. linear regression) have a single global minimum
- **Non-convex problems** (neural networks) have many local minima and saddle points

## The Update Rule

For each training step, we compute the gradient and step opposite to it:

\`\`\`
θ_new = θ_old - α × ∇L(θ_old)
\`\`\`

The gradient ∇L tells us the direction of steepest *ascent*, so we negate it to descend.

## Learning Rate Selection

The learning rate α is arguably the most critical hyperparameter:

- **Too large**: Loss oscillates or diverges
- **Too small**: Training is glacially slow, may get stuck in local minima
- **Adaptive methods**: Adam, RMSProp, AdaGrad adjust α per-parameter based on gradient history

## Mini-Batch Gradient Descent

Computing the gradient over the entire dataset (batch GD) is expensive. In practice:

- **Stochastic GD (SGD)**: Update on each individual example — noisy but fast
- **Mini-batch GD**: Update on batches of 32–512 examples — balances noise and efficiency
- The noise in SGD can actually help escape shallow local minima

## Momentum

Standard gradient descent can oscillate in ravine-shaped regions. Momentum solves this by accumulating a velocity vector:

\`\`\`
v_t = β × v_{t-1} + (1-β) × ∇L
θ   = θ - α × v_t
\`\`\`

With β ≈ 0.9, the optimizer effectively looks at a weighted average of recent gradients.

## The Vanishing Gradient Problem

In deep networks, gradients flow backward through many layers via the chain rule. If activation functions have small derivatives (e.g. saturated sigmoid), gradients can shrink exponentially:

- **Symptom**: Early layers barely learn; later layers adapt fine
- **Solutions**: ReLU activations, skip connections (ResNets), batch normalization, careful initialization

## Key Takeaways

Modern training uses Adam (Adaptive Moment Estimation) which combines momentum and per-parameter adaptive learning rates. For most problems, Adam with lr=1e-3 is a reasonable default.`,
  key_takeaways: [
    'Always start with Adam optimizer at lr=1e-3 and tune from there',
    'Monitor both training and validation loss to catch overfitting early',
    'Batch normalization stabilizes training and mitigates vanishing gradients',
    'Learning rate schedules (cosine annealing, reduce-on-plateau) consistently improve final accuracy',
    'Gradient clipping prevents exploding gradients in RNNs and transformers',
  ],
  visual_summary:
    'The presenter uses animated diagrams to show a 3D loss landscape with gradient vectors. Several whiteboard illustrations demonstrate the update rule, learning rate effects, and momentum accumulation. Code snippets in Python show PyTorch and TensorFlow implementations.',
  scenes: [
    { scene_label: 'Introduction & Overview', description: 'Presenter introduces the core problem of optimization in machine learning.' },
    { scene_label: 'The Loss Function', description: 'Animated 3D surface plot of a loss landscape with the global minimum highlighted.' },
    { scene_label: 'Gradient Vectors', description: 'Whiteboard diagram showing gradient vectors pointing uphill and the update rule stepping downhill.' },
    { scene_label: 'Learning Rate Demo', description: 'Side-by-side animation: too-large learning rate overshooting, too-small crawling, optimal converging smoothly.' },
    { scene_label: 'Mini-Batch Training', description: 'Visualization of data batches being sampled and noisy gradient descent paths.' },
    { scene_label: 'Momentum Explained', description: 'Ball-rolling-down-hill analogy with velocity accumulation arrows.' },
    { scene_label: 'Vanishing Gradients', description: 'Deep network diagram with shrinking gradient bars as they flow backward.' },
    { scene_label: 'Adam Optimizer', description: 'Comparison table of SGD vs Momentum vs RMSProp vs Adam convergence speeds.' },
  ],
  confidence_notes: 'High confidence throughout. All sections supported by clear audio explanation and matching visual content.',
}

export const MOCK_SCENES = MOCK_NOTES.scenes.map((s, i) => ({
  id: i + 1,
  scene_number: i + 1,
  start_time: i * 45,
  end_time: (i + 1) * 45,
  keyframe_path: null as string | null,
  description: s.description,
  scene_label: s.scene_label,
}))

export const MOCK_ANALYTICS = {
  word_frequency: [
    { word: 'gradient',   count: 42 },
    { word: 'learning',   count: 38 },
    { word: 'loss',       count: 35 },
    { word: 'rate',       count: 31 },
    { word: 'training',   count: 29 },
    { word: 'function',   count: 26 },
    { word: 'parameters', count: 23 },
    { word: 'descent',    count: 21 },
    { word: 'neural',     count: 19 },
    { word: 'momentum',   count: 17 },
    { word: 'batch',      count: 15 },
    { word: 'optimizer',  count: 14 },
  ],
  top_topics: ['Gradient Descent', 'Neural Networks', 'Optimization', 'Backpropagation', 'Adam'],
  scene_count: 8,
  duration: 360,
  words_per_minute: 148,
  speaking_ratio: 0.87,
  total_words: 888,
}
