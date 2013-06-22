/*global THREE*/

var Scene = function() {

var camera, scene, mesh, renderer, loader;
var ground, geometry, pivot;
var currentMesh = "";
var has_gl = false;
var clock = new THREE.Clock();

var definedmodels = true;
if (typeof (models) == 'undefined')
    definedmodels = false;



var initControls = function() {
    $('#canvas').show();
    $('#selectModel').empty();

    if (definedmodels) {
        var i;
        for ( i in models ) {
            $('#selectModel').append($('<option></option>').attr("value", i).text(i));
        }
    }
    else {
        $('#selectModelInput').hide();
    }

    /*$('#selectFileInput').parentNode.replaceChild(
        fileInputElement.cloneNode(true),
        fileInputElement
    );*/
    // Check for the various File API support.
    if (!(window.File && window.FileReader && window.FileList)) {
        $('#selectFileInput').remove();
    }

};


var initBindings = function(canvas) {

    var rect = canvas.getBoundingClientRect();
    var oldPos = {
        x: 0,
        y: 0
    };
    var newPos = {
        x: 0,
        y: 0
    };

    var isRotating = false;
    var isPanning = false;

    $(canvas).on("mousedown", function(event) {
        if (event.which === 1) {
            isRotating = true;
        }
        else if (event.which === 2) {
            isPanning = true;
        }
        oldPos = {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top
        };
    });

    $(canvas).on("mouseup", function(event) {
        if (event.which === 1) {
            isRotating = false;
        }
        else if (event.which === 2) {
            isPanning = false;
        }
        oldPos = {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top
        };
    });

    $(canvas).on("mousemove", function(event) {
        if (!isRotating && !isPanning) {
            return;
        }

        event.preventDefault();
        newPos = {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top
        };

        if ( isRotating ) {
            pivot.rotation.y += (newPos.x - oldPos.x) / 100;
            pivot.rotation.x += (newPos.y - oldPos.y) / 100;
        }
        else if ( isPanning ) {
            camera.position.x -= 0.1 * (newPos.x - oldPos.x);
            camera.position.y += 0.1 * (newPos.y - oldPos.y);
        }

        oldPos = newPos;
    });

    $(canvas).on('mousewheel', function(event, delta, deltaX, deltaY) {
        event.preventDefault();
        if ( ( camera.position.z > 0 && camera.position.z < 10000 ) ||
         ( camera.position.z <= 0 && deltaY < 0 ) ||
         ( camera.position.z >= 10000 && deltaY > 0 ) ){
        camera.position.z -= deltaY;
        }
    });

    $(window).resize( function() {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize( window.innerWidth, window.innerHeight );
    });

    $('#loadModel').on("click", function(event) {
        var name = $('#selectModel').find(":selected").text();
        var path = models[name];
        loadModel(path);
    });


    $("#selectFile").change( function(evt) {
        var f = evt.target.files[0]; // FileList object
        var reader = new FileReader();

        reader.onload = function(e) {
            loadFile(e.target.result);
        };

        reader.readAsDataURL( f );
        //reader.readAsText( f );
    });

};



var clearBindings = function() {
    var canvas;

    $('#loadModel').off("click");

    $('#controls').hide();
    $('#canvas').hide();

    if ( canvas !== undefined ) {
        canvas = renderer.domElement;
        $(canvas).off("mousedown");
        $(canvas).off("mousemove");
        $(canvas).off("mouseup");
    }
};


var createRenderer = function() {
    var canvas;

    try {
        renderer = new THREE.WebGLRenderer( /*{ antialias: true }*/ );
        renderer.setSize( window.innerWidth, window.innerHeight );

        //renderer.gammaInput = true;
        //renderer.gammaOutput = true;
        renderer.physicallyBasedShading = true;
        renderer.shadowMapEnabled = true;

        canvas = renderer.domElement;
        render();
        has_gl = true;
    }
    catch (e) {
        has_gl = false;
    }

    $('#canvas').empty();

    if (has_gl) {
        $('#canvas').append( canvas );
        initBindings(canvas);
    }
    else {
        $('body').append($('<h2></h2>').text("Please install a web browser that supports WebGL."));
    }
};



var init = function() {
    clearBindings();
    createRenderer();

    if (has_gl) {
        initControls();

        scene = new THREE.Scene();


        camera = new THREE.PerspectiveCamera( 35, window.innerWidth / window.innerHeight, 1, 10000 );
        camera.position.z = 25;
        camera.position.y = 5;


        loader = new THREE.JSONLoader( true );
        loader.onLoadStart = onLoadStart;
        loader.onLoadProgress = onLoadProgress;
        loader.onLoadComplete = onLoadComplete;

        $('#status').empty();
        $('#status').append( loader.statusDomElement );


        var light = new THREE.DirectionalLight( 0xFFFFFF );
        light.position.set( 50, 50, 50 );

        light.castShadow = true;
        light.shadowDarkness = 0.3;
        light.shadowMapWidth = 2048;
        light.shadowMapHeight = 2048;

        var d = 20
        light.shadowCameraLeft = -d * 2;
        light.shadowCameraRight = d * 2;
        light.shadowCameraTop = d;
        light.shadowCameraBottom = -d;
        light.shadowCameraFar = 100;
        scene.add(light);


        scene.fog = new THREE.Fog( 0xE0E0E0, 15, 100 );
        renderer.setClearColor( scene.fog.color, 1 );


        //ground
        var x = document.createElement("canvas");
        var xc = x.getContext("2d");
        x.width = x.height = 128;
        xc.fillStyle = "#999";
        xc.fillRect(0, 0, 128, 128);
        xc.fillStyle = "#777";
        xc.fillRect(0, 0, 64, 64);
        xc.fillStyle = "#777";
        xc.fillRect(64, 64, 64, 64);

        var map = new THREE.Texture( x, new THREE.UVMapping(), THREE.RepeatWrapping, THREE.RepeatWrapping );
        map.needsUpdate = true;
        map.repeat.set( 60, 60 );


        var xm = new THREE.MeshLambertMaterial( { map: map, emissive: 0x999999, perPixel: true } );
        geometry = new THREE.PlaneGeometry( 256, 256 );
        geometry.applyMatrix( new THREE.Matrix4().makeRotationX(-1.5707963267948966) );

        ground = new THREE.Mesh( geometry, xm );
        ground.receiveShadow = true;
        ground.position.set(0,-5,0)


        pivot = new THREE.Object3D();
        pivot.position.y = 5;
        pivot.add(ground);

        scene.add(pivot);


        if (definedmodels)
            loadModel( models[$('#selectModel').find(":selected").text()] );
    }
};


var unloadCurrentModel = function() {
    if ( mesh instanceof THREE.Mesh ) {
        pivot.remove(mesh);
    }
};

var onLoadStart = function() {
    loader.statusDomElement.innerHTML = "Starting to load model.";
};

var onLoadProgress = function() {
    loader.statusDomElement.innerHTML = "Loading...";
};

var onLoadComplete = function() {
    loader.statusDomElement.innerHTML = "Finished loading model.";
};


var loadModel = function( path ) {
    unloadCurrentModel();
    loader.load( path, function( geometry, materials ) {
        loadGeometry(geometry, materials);
    });
};

var loadFile = function( path ) {
    unloadCurrentModel();

    /*var parsed = JSON.parse(text);
    var model = loader.parse(parsed);
    loadGeometry(model.geometry, model.materials);*/

    loader.loadAjaxJSON( loader, path,
        function( geometry, materials ) {
            loadGeometry(geometry, materials);
        }
    );
};

var loadGeometry = function(geometry, materials) {

    var skinned = true;
    if (typeof (geometry.bones) == 'undefined')
        skinned = false;


    if (skinned) {
        ensureLoop( geometry.animation );
        THREE.AnimationHandler.add( geometry.animation );
        mesh = new THREE.SkinnedMesh( geometry, new THREE.MeshFaceMaterial(materials) );
    }
    else {
        mesh = new THREE.Mesh( geometry, new THREE.MeshFaceMaterial(materials) );
    }


    for ( var i = 0; i < materials.length; i ++ ) {
        var m = materials[ i ];
        if (skinned) m.skinning = true;
        m.wrapAround = true;
        m.perPixel = true;
    }


    geometry.computeBoundingBox();
    var bb = geometry.boundingBox;

    var s = 1/(bb.max.y - bb.min.y) * 10;
    var x = 0 - s*(bb.min.x + bb.max.x)/2;
    var y = 0 - s*(bb.min.y + bb.max.y)/2;
    var z = 0 - s*(bb.min.z + bb.max.z)/2;

    mesh.position.set( x, y, z );
    mesh.scale.set( s, s, s );

    mesh.castShadow = true;
    mesh.receiveShadow = true;

    pivot.rotation.set(0,0,0);
    pivot.add(mesh);

    if (skinned) {
        animation = new THREE.Animation( mesh, geometry.animation.name );
        animation.JITCompile = false;
        animation.interpolationType = THREE.AnimationHandler.LINEAR;

        animation.play();
    }
};


var ensureLoop = function ( animation ) {

    for ( var i = 0; i < animation.hierarchy.length; i ++ ) {

        var bone = animation.hierarchy[ i ];

        var first = bone.keys[ 0 ];
        var last = bone.keys[ bone.keys.length - 1 ];

        last.pos = first.pos;
        last.rot = first.rot;
        last.scl = first.scl;
    }
}


var render = function() {
    requestAnimationFrame( render );

    var delta = 0.75 * clock.getDelta();
    THREE.AnimationHandler.update( delta );

    if ( scene !== undefined && camera !== undefined ) {
         renderer.render( scene, camera );
    }
    //stats.update();
}


return {
init: init
};

}();