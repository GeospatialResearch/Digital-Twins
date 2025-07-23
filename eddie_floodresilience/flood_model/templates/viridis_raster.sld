<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                       xsi:schemaLocation="http://www.opengis.net/sld
http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd" version="1.0.0">
    <NamedLayer>
        <Name>viridis_raster</Name>
        <UserStyle>
            <Title>Viridis Raster</Title>
            <FeatureTypeStyle>
                <Rule>
                    <RasterSymbolizer>
                        <ColorMap>
                            <ColorMapEntry color="#fde725" quantity="0" label="0.0m" opacity="0"/>
                            <ColorMapEntry color="#fde725" quantity="0.1" label="0.1m" opacity="1"/>
                            <ColorMapEntry color="#7ad151" quantity="1" label="1.0m"/>
                            <ColorMapEntry color="#22a884" quantity="2" label="2.0m"/>
                            <ColorMapEntry color="#2a788e" quantity="3" label="3.0m"/>
                            <ColorMapEntry color="#414487" quantity="4" label="4.0m"/>
                            <ColorMapEntry color="#440154" quantity="5" label="5.0m"/>
                        </ColorMap>
                        <Opacity>1.0</Opacity>
                    </RasterSymbolizer>
                </Rule>
            </FeatureTypeStyle>
        </UserStyle>
    </NamedLayer>
</StyledLayerDescriptor>
