"""Named FLUX image-style presets.

Profiles reference these by name (e.g. ``image_styles=["macro_chip", "blueprint"]``)
so each blog has a consistent visual identity. A profile with no styles uses the
whole catalog. The per-post pick is deterministic (hash of the title) — see
``blogkit.core.imager``.
"""

from __future__ import annotations

STYLE_PRESETS: dict[str, str] = {
    # --- originals ---
    "cinematic_editorial": (
        "cinematic editorial photograph, shallow depth of field, dramatic natural "
        "lighting, photorealistic, shot on 35mm, ultra detailed, 8k"
    ),
    "architectural_wide": (
        "wide cinematic establishing shot of a sleek modern high-tech environment, "
        "volumetric light, realistic materials, professional architectural photography"
    ),
    "macro_product": (
        "premium macro product photography, intricate detail, soft studio lighting, "
        "rich bokeh, hyper realistic"
    ),
    "isometric_3d": (
        "sleek isometric 3D render, clean corporate infographic aesthetic, soft "
        "gradients, subtle depth of field, octane render"
    ),
    "data_flow": (
        "abstract data-flow visualization, glowing interconnected network nodes and "
        "lines on a dark background, futuristic, elegant, depth"
    ),
    "conceptual_still_life": (
        "minimalist conceptual still life, one bold symbolic subject, premium muted "
        "color palette, soft directional shadows, gallery lighting"
    ),
    # --- B2B tech-specialized ---
    "glassmorphism": (
        "modern glassmorphism 3D render, translucent frosted glass shapes, "
        "floating tech elements, soft pastel gradient background, ultra clean, 8k"
    ),
    "double_exposure": (
        "sophisticated double exposure photography, blending a corporate business "
        "silhouette with glowing fiber optic data networks, cinematic, highly detailed"
    ),
    "papercraft": (
        "elegant minimalist 3D papercraft art, layered clean white paper, "
        "subtle colored backlighting, corporate tech metaphor, highly detailed"
    ),
    "macro_chip": (
        "extreme macro photography of a silicon microchip, glowing circuitry pathways, "
        "iridescent gold and blue reflections, hyper-detailed tech photography"
    ),
    "blueprint": (
        "futuristic architectural blueprint schematic, glowing neon cyan and gold lines "
        "on dark navy grid, technical data visualization, precise engineering"
    ),
    "server_room": (
        "cinematic server room interior, moody dark tech atmosphere, glowing led "
        "indicator lights, shallow depth of field, photorealistic, 8k"
    ),
    "hologram_ar": (
        "glowing futuristic 3D hologram floating in a dark modern office setting, "
        "volumetric light rays, augmented reality interface, photorealistic"
    ),
    "low_poly": (
        "sleek low poly 3D geometric landscape, corporate tech aesthetic, "
        "smooth shading, ambient occlusion, crisp edges, professional color palette"
    ),
    "editorial_illustration": (
        "sophisticated modern editorial illustration, fluid watercolor and ink, "
        "tech business concept, muted corporate colors, elegant and expressive"
    ),
    "surreal_business": (
        "surreal conceptual photography, floating glowing geometric spheres over a "
        "minimalist concrete desk, dramatic lighting, luxury editorial style"
    ),
}

ALL_STYLE_NAMES: list[str] = list(STYLE_PRESETS)
