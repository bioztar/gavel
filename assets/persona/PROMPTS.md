# Avatar prompts

Generated with `fal-ai/flux/schnell`, 1024x1024.

## chair-01.png

```
Studio portrait photo of a calm, professional meeting chairperson, a woman in her 40s with short dark hair, wearing a simple navy blazer, front-facing, direct eye contact with camera, head and shoulders, neutral plain gray background, even soft studio lighting, sharp focus, photorealistic, high detail, 85mm lens, no text, no watermark, no logo
```

## chair-02.png

```
Studio portrait photo of a calm, professional meeting chairperson, a man in his 50s with gray hair and glasses, wearing a light gray sweater, front-facing, direct eye contact with camera, head and shoulders, neutral plain gray background, even soft studio lighting, sharp focus, photorealistic, high detail, 85mm lens, no text, no watermark, no logo
```

## chair-03.png

```
Studio portrait photo of a calm, professional meeting chairperson, a woman in her 30s with shoulder-length black hair, wearing a charcoal blazer, front-facing, direct eye contact with camera, head and shoulders, neutral plain gray background, even soft studio lighting, sharp focus, photorealistic, high detail, 85mm lens, no text, no watermark, no logo
```

## chair-04.png

```
Studio portrait photo of a calm, professional meeting chairperson, a man in his 40s with short black hair and a beard, wearing a dark blue shirt, front-facing, direct eye contact with camera, head and shoulders, neutral plain gray background, even soft studio lighting, sharp focus, photorealistic, high detail, 85mm lens, no text, no watermark, no logo
```

## Funky Karen

chair-03 is now `karen-formal.png` (identical pixels, just renamed/copied so nothing
that already points at `chair-03.png` breaks). The three funky candidates are
`fal-ai/flux/dev/image-to-image` off `karen-formal.png` — same woman, same face,
different wardrobe/lighting/background so a judge can tell the two personas apart
from a few meters away.

Two earlier passes (strength=0.6, then 0.8 with funky-first wording) both still
read as formal Karen — black blazer and gray background survived the denoise.
What worked: strength 0.9, specific colours/materials instead of vague words
("loud patterned" -> "red-and-orange floral-print"), and a short identity clause
instead of a long one. funky-02 alone needed a third pass at strength=0.82 because
the 0.9 version turned her head away from the camera, breaking the front-facing/
direct-eye-contact requirement a talking-head render needs.

### karen-funky-01.png

```
wearing a bright red-and-orange floral-print blazer over a bold striped top, big round tortoiseshell glasses with amber-tinted lenses, standing against a solid bright coral-orange wall, same identifiable woman's face, direct eye contact with camera, head and shoulders, mouth fully visible and unobstructed, photorealistic, no text, no watermark, no logo
```
strength=0.9

### karen-funky-02.png

```
front-facing portrait, looking directly into the camera, head and shoulders, under dramatic nightclub lighting: intense hot-magenta light glowing across the left side of her face and hair, bright cyan light glowing across the right side, wearing a sparkling silver sequin jacket, dark navy background with soft neon glow, same identifiable woman's face, mouth fully visible and unobstructed, photorealistic, no text, no watermark, no logo
```
strength=0.82

### karen-funky-03.png

```
wearing a bright mustard-yellow cardigan, hair pulled up in a messy bun with a yellow pencil stuck through it, large colourful geometric earrings, standing in front of a cork bulletin board covered edge to edge with colourful sticky notes, same identifiable woman's face, direct eye contact with camera, head and shoulders, mouth fully visible and unobstructed, photorealistic, no text, no watermark, no logo
```
strength=0.9
